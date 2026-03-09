from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from higgs_agent.analytics import AnalyticsFilter, aggregate_attempt_summaries
from higgs_agent.benchmarking import (
    BenchmarkCandidate,
    BenchmarkHarnessConfig,
    BenchmarkQualitySignal,
    build_benchmark_report,
    load_benchmark_workload_manifest,
    run_benchmark_workload,
)
from higgs_agent.events.records import AttemptSummaryBuilder, EventStreamBuilder
from higgs_agent.providers.contract import ExecutorInput, ProviderExecutionResult, ProviderUsage
from higgs_agent.routing import RouteDecision


class FakeExecutor:
    def __init__(self, result_factory) -> None:
        self._result_factory = result_factory

    def execute(
        self, execution_input: ExecutorInput, *, tool_invoker=None
    ) -> ProviderExecutionResult:
        return self._result_factory(execution_input)


def test_benchmark_pipeline_outputs_compatible_with_observability_contracts() -> None:
    workload = load_benchmark_workload_manifest().workloads[1]
    harness_result = run_benchmark_workload(
        workload,
        (
            BenchmarkCandidate(
                "balanced",
                _route(workload, "openrouter", "openai/gpt-4o", "balanced"),
                FakeExecutor(
                    lambda execution_input: _succeeded_result(
                        execution_input, latency_ms=300, cost_usd=0.04
                    )
                ),
            ),
            BenchmarkCandidate(
                "deep",
                _route(workload, "openrouter", "anthropic/claude-3.5-sonnet", "deep"),
                FakeExecutor(
                    lambda execution_input: _succeeded_result(
                        execution_input, latency_ms=220, cost_usd=0.06
                    )
                ),
            ),
        ),
        config=BenchmarkHarnessConfig(benchmark_id="bench-contract-1", repo_head="abc123"),
    )

    report = build_benchmark_report(
        harness_result,
        quality_signals_by_candidate={
            "balanced": (
                BenchmarkQualitySignal("rubric_accuracy", 0.82, "Solid tradeoff summary"),
            ),
            "deep": (BenchmarkQualitySignal("rubric_accuracy", 0.91, "More complete reasoning"),),
        },
    )

    for candidate_result in harness_result.candidate_results:
        _validate_event_stream(candidate_result.execution_result.events)
        _validate_attempt_summary(candidate_result.execution_result.attempt_summary)

    analytics_report = aggregate_attempt_summaries(
        tuple(
            candidate_result.execution_result.attempt_summary
            for candidate_result in harness_result.candidate_results
        ),
        {
            f"BENCH-{workload.workload_id}": {
                "ticket_type": workload.ticket_shape.work_type,
                "ticket_priority": workload.ticket_shape.priority,
                "higgs_platform": workload.ticket_shape.platform,
                "higgs_complexity": workload.ticket_shape.complexity,
            }
        },
        AnalyticsFilter(group_by=("provider", "model", "ticket_type")),
    )

    assert len(analytics_report.records) == 2
    for record in analytics_report.records:
        _validate_aggregate(record)

    payload = report.to_dict()
    json.dumps(payload)
    assert payload["candidates"][0]["ranking_inputs"]["quality_signal_avg"] == 0.91
    assert payload["candidates"][0]["raw_metrics"]["status"] == "succeeded"
    assert "raw_prompt" not in json.dumps(payload)


def test_benchmark_pipeline_is_reproducible_for_fixed_inputs_and_surfaces_partial_failures() -> (
    None
):
    workload = load_benchmark_workload_manifest().workloads[0]

    def build_report() -> dict[str, object]:
        harness_result = run_benchmark_workload(
            workload,
            (
                BenchmarkCandidate(
                    "docs-success",
                    _route(workload, "openrouter", "openai/gpt-4o-mini", "economy"),
                    FakeExecutor(
                        lambda execution_input: _succeeded_result(
                            execution_input, latency_ms=180, cost_usd=0.02
                        )
                    ),
                ),
                BenchmarkCandidate(
                    "docs-failure",
                    _route(workload, "local", "local/llama3.1:8b", "local"),
                    FakeExecutor(_failed_result_without_precise_cost),
                ),
            ),
            config=BenchmarkHarnessConfig(benchmark_id="bench-repro-1"),
        )
        return build_benchmark_report(harness_result).to_dict()

    first = build_report()
    second = build_report()

    assert first["ranking_policy"] == second["ranking_policy"]
    assert [candidate["candidate_id"] for candidate in first["candidates"]] == [
        candidate["candidate_id"] for candidate in second["candidates"]
    ]
    assert first["candidates"][1]["raw_metrics"]["final_result"] == "failed"
    assert "non_success_result:failed" in first["candidates"][1]["comparison_notes"]
    assert "cost_unavailable" in first["candidates"][1]["comparison_notes"]
    assert first["candidates"][1]["ranking_inputs"]["cost_usd"] is None


def _route(workload, provider: str, model_id: str, route_family: str) -> RouteDecision:
    return RouteDecision(
        ticket_id=workload.workload_id,
        priority=workload.ticket_shape.priority,
        selected=True,
        provider=provider,
        model_id=model_id,
        route_family=route_family,
        estimated_cost_usd=1.0,
        requires_tool_calls=workload.ticket_shape.tool_profile != "none",
        blocked_reason=None,
        rationale=(f"selected_model:{model_id}",),
    )


def _succeeded_result(
    execution_input: ExecutorInput,
    *,
    latency_ms: int,
    cost_usd: float,
) -> ProviderExecutionResult:
    usage = ProviderUsage(
        tokens_prompt=12,
        tokens_completion=8,
        total_tokens=20,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
    events = EventStreamBuilder(
        run_id=execution_input.run_id,
        attempt_id=execution_input.attempt_id,
        ticket_id=execution_input.ticket_id,
        executor_version=execution_input.executor_version,
        repo_head=execution_input.repo_head,
    )
    events.append(
        "route.selected",
        "succeeded",
        payload={
            "provider": execution_input.route.provider,
            "model": execution_input.route.model_id,
            "route_family": execution_input.route.route_family,
        },
    )
    events.append("provider.responded", "succeeded", usage=usage)
    summary = AttemptSummaryBuilder(
        run_id=execution_input.run_id,
        attempt_id=execution_input.attempt_id,
        ticket_id=execution_input.ticket_id,
        started_at="2026-03-07T21:00:00Z",
    ).build(
        final_result="succeeded",
        provider=execution_input.route.provider,
        model=execution_input.route.model_id,
        tool_call_count=0,
        retry_count=0,
        usage=usage,
        ended_at="2026-03-07T21:00:01Z",
    )
    return ProviderExecutionResult(
        status="succeeded",
        output_text="ok",
        tool_calls=(),
        usage=usage,
        events=events.build(),
        attempt_summary=summary,
        retry_count=0,
        metadata={"benchmark_candidate": execution_input.route.model_id},
    )


def _failed_result_without_precise_cost(execution_input: ExecutorInput) -> ProviderExecutionResult:
    usage = ProviderUsage(tokens_prompt=10, tokens_completion=4, total_tokens=14, latency_ms=450)
    events = EventStreamBuilder(
        run_id=execution_input.run_id,
        attempt_id=execution_input.attempt_id,
        ticket_id=execution_input.ticket_id,
        executor_version=execution_input.executor_version,
        repo_head=execution_input.repo_head,
    )
    events.append(
        "route.selected",
        "succeeded",
        payload={
            "provider": execution_input.route.provider,
            "model": execution_input.route.model_id,
            "route_family": execution_input.route.route_family,
        },
    )
    events.append(
        "provider.responded",
        "failed",
        usage=usage,
        error={"kind": "provider", "message": "benchmark failure"},
    )
    summary = AttemptSummaryBuilder(
        run_id=execution_input.run_id,
        attempt_id=execution_input.attempt_id,
        ticket_id=execution_input.ticket_id,
        started_at="2026-03-07T21:00:00Z",
    ).build(
        final_result="failed",
        provider=execution_input.route.provider,
        model=execution_input.route.model_id,
        tool_call_count=0,
        retry_count=1,
        usage=usage,
        error={"kind": "provider", "message": "benchmark failure"},
        ended_at="2026-03-07T21:00:02Z",
    )
    return ProviderExecutionResult(
        status="failed",
        output_text="",
        tool_calls=(),
        usage=usage,
        events=events.build(),
        attempt_summary=summary,
        retry_count=1,
        metadata={"benchmark_candidate": execution_input.route.model_id},
    )


def _validate_event_stream(events: tuple[dict[str, object], ...]) -> None:
    event_schema = json.loads(Path("schemas/execution-event.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = (
        Registry()
        .with_resource(
            common_defs["$id"],
            Resource.from_contents(common_defs),
        )
        .with_resource(
            "common-defs.schema.json",
            Resource.from_contents(common_defs),
        )
    )
    validator = jsonschema.Draft202012Validator(event_schema, registry=registry)
    for event in events:
        validator.validate(event)


def _validate_attempt_summary(summary: dict[str, object]) -> None:
    summary_schema = json.loads(Path("schemas/execution-attempt.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = (
        Registry()
        .with_resource(
            common_defs["$id"],
            Resource.from_contents(common_defs),
        )
        .with_resource(
            "common-defs.schema.json",
            Resource.from_contents(common_defs),
        )
    )
    jsonschema.Draft202012Validator(summary_schema, registry=registry).validate(summary)


def _validate_aggregate(record: dict[str, object]) -> None:
    aggregate_schema = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())
    jsonschema.validate(record, aggregate_schema)
