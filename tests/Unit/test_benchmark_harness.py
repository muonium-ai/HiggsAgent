from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from higgs_agent.benchmarking import (
    BenchmarkCandidate,
    BenchmarkHarnessConfig,
    BenchmarkHarnessError,
    load_benchmark_workload_manifest,
    run_benchmark_workload,
)
from higgs_agent.events.records import AttemptSummaryBuilder, EventStreamBuilder
from higgs_agent.providers.contract import (
    ExecutorInput,
    ProviderExecutionResult,
    ProviderToolDefinition,
    ProviderUsage,
)
from higgs_agent.routing import RouteDecision


class FakeExecutor:
    def __init__(self, result_factory) -> None:
        self._result_factory = result_factory
        self.calls: list[ExecutorInput] = []

    def execute(self, execution_input: ExecutorInput, *, tool_invoker=None) -> ProviderExecutionResult:
        self.calls.append(execution_input)
        return self._result_factory(execution_input)


def test_benchmark_harness_executes_same_workload_with_shared_control_plane() -> None:
    workload = load_benchmark_workload_manifest().workloads[1]
    executor_a = FakeExecutor(lambda execution_input: _result_for(execution_input, output_text="A"))
    executor_b = FakeExecutor(lambda execution_input: _result_for(execution_input, output_text="B"))

    result = run_benchmark_workload(
        workload,
        (
            BenchmarkCandidate("balanced", _route(workload, "openrouter", "openai/gpt-4o", "balanced"), executor_a),
            BenchmarkCandidate("deep", _route(workload, "openrouter", "anthropic/claude-3.5-sonnet", "deep"), executor_b),
        ),
        config=BenchmarkHarnessConfig(
            benchmark_id="bench-spec-1",
            system_prompt="Benchmark evaluator",
            repo_head="abc123",
        ),
    )

    assert result.benchmark_id == "bench-spec-1"
    assert result.shared_execution_context["candidate_ids"] == ["balanced", "deep"]
    assert len(result.candidate_results) == 2
    assert executor_a.calls[0].prompt == executor_b.calls[0].prompt
    assert executor_a.calls[0].system_prompt == executor_b.calls[0].system_prompt == "Benchmark evaluator"
    assert executor_a.calls[0].repo_head == executor_b.calls[0].repo_head == "abc123"
    assert executor_a.calls[0].allow_tool_calls is True
    assert executor_b.calls[0].allow_tool_calls is True
    assert executor_a.calls[0].ticket_id == executor_b.calls[0].ticket_id == "BENCH-spec-routing-tradeoff-analysis"
    assert result.candidate_results[0].execution_result.output_text == "A"
    assert result.candidate_results[1].execution_result.output_text == "B"
    _validate_event_stream(result.candidate_results[0].execution_result.events)
    _validate_attempt_summary(result.candidate_results[0].execution_result.attempt_summary)


def test_benchmark_harness_rejects_repository_write_workloads() -> None:
    workload = replace(load_benchmark_workload_manifest().workloads[0], requires_repository_write=True)

    with pytest.raises(BenchmarkHarnessError, match="repository writes are unsupported"):
        run_benchmark_workload(
            workload,
            (BenchmarkCandidate("docs", _route(workload, "openrouter", "openai/gpt-4o-mini", "economy"), FakeExecutor(_result_for)),),
            config=BenchmarkHarnessConfig(benchmark_id="bench-write-1"),
        )


def test_benchmark_harness_rejects_incomparable_candidate_tool_requirements() -> None:
    workload = load_benchmark_workload_manifest().workloads[0]

    with pytest.raises(BenchmarkHarnessError, match="tool-call requirement must match the workload tool profile"):
        run_benchmark_workload(
            workload,
            (
                BenchmarkCandidate(
                    "bad-tools",
                    replace(_route(workload, "openrouter", "openai/gpt-4o-mini", "economy"), requires_tool_calls=True),
                    FakeExecutor(_result_for),
                ),
            ),
            config=BenchmarkHarnessConfig(benchmark_id="bench-tools-1"),
        )


def test_benchmark_harness_rejects_configured_tools_for_toolless_workload() -> None:
    workload = load_benchmark_workload_manifest().workloads[0]

    with pytest.raises(
        BenchmarkHarnessError,
        match="tools are unsupported when the workload tool profile is none",
    ):
        run_benchmark_workload(
            workload,
            (
                BenchmarkCandidate(
                    "docs",
                    _route(workload, "openrouter", "openai/gpt-4o-mini", "economy"),
                    FakeExecutor(_result_for),
                ),
            ),
            config=BenchmarkHarnessConfig(
                benchmark_id="bench-tools-2",
                tools=(
                    ProviderToolDefinition(
                        name="read_ticket",
                        description="Read ticket context",
                        parameters={"type": "object"},
                    ),
                ),
            ),
        )


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


def _result_for(execution_input: ExecutorInput, output_text: str = "ok") -> ProviderExecutionResult:
    usage = ProviderUsage(tokens_prompt=10, tokens_completion=5, total_tokens=15, cost_usd=0.01, latency_ms=250)
    event_builder = EventStreamBuilder(
        run_id=execution_input.run_id,
        attempt_id=execution_input.attempt_id,
        ticket_id=execution_input.ticket_id,
        executor_version=execution_input.executor_version,
        repo_head=execution_input.repo_head,
    )
    event_builder.append(
        "route.selected",
        "succeeded",
        payload={
            "provider": execution_input.route.provider,
            "model": execution_input.route.model_id,
            "route_family": execution_input.route.route_family,
            "rationale": list(execution_input.route.rationale),
        },
    )
    event_builder.append("provider.responded", "succeeded", usage=usage)
    attempt_summary = AttemptSummaryBuilder(
        run_id=execution_input.run_id,
        attempt_id=execution_input.attempt_id,
        ticket_id=execution_input.ticket_id,
        started_at="2026-03-07T20:00:00Z",
    ).build(
        final_result="succeeded",
        provider=execution_input.route.provider,
        model=execution_input.route.model_id,
        tool_call_count=0,
        retry_count=0,
        usage=usage,
        ended_at="2026-03-07T20:00:01Z",
    )
    return ProviderExecutionResult(
        status="succeeded",
        output_text=output_text,
        tool_calls=(),
        usage=usage,
        events=event_builder.build(),
        attempt_summary=attempt_summary,
        retry_count=0,
        metadata={"benchmark_candidate": execution_input.route.model_id},
    )


def _validate_event_stream(events: tuple[dict[str, object], ...]) -> None:
    event_schema = json.loads(Path("schemas/execution-event.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = Registry().with_resource(
        common_defs["$id"],
        Resource.from_contents(common_defs),
    ).with_resource(
        "common-defs.schema.json",
        Resource.from_contents(common_defs),
    )
    validator = jsonschema.Draft202012Validator(event_schema, registry=registry)
    for event in events:
        validator.validate(event)


def _validate_attempt_summary(summary: dict[str, object]) -> None:
    summary_schema = json.loads(Path("schemas/execution-attempt.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = Registry().with_resource(
        common_defs["$id"],
        Resource.from_contents(common_defs),
    ).with_resource(
        "common-defs.schema.json",
        Resource.from_contents(common_defs),
    )
    jsonschema.Draft202012Validator(summary_schema, registry=registry).validate(summary)