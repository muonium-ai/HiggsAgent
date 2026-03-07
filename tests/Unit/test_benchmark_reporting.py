from __future__ import annotations

from higgs_agent.benchmarking import (
    BenchmarkCandidate,
    BenchmarkHarnessConfig,
    BenchmarkQualitySignal,
    build_benchmark_report,
    load_benchmark_workload_manifest,
    render_benchmark_report_table,
    run_benchmark_workload,
)
from higgs_agent.providers.contract import ProviderExecutionResult, ProviderUsage
from higgs_agent.routing import RouteDecision

from tests.Unit.test_benchmark_harness import FakeExecutor, _result_for


def test_benchmark_report_exposes_raw_metrics_and_explicit_quality_signals() -> None:
    workload = load_benchmark_workload_manifest().workloads[1]
    harness_result = run_benchmark_workload(
        workload,
        (
            BenchmarkCandidate(
                "balanced",
                _route(workload, "openrouter", "openai/gpt-4o", "balanced"),
                FakeExecutor(lambda execution_input: _result_for(execution_input, output_text="balanced")),
            ),
            BenchmarkCandidate(
                "deep",
                _route(workload, "openrouter", "anthropic/claude-3.5-sonnet", "deep"),
                FakeExecutor(lambda execution_input: _result_for(execution_input, output_text="deep")),
            ),
        ),
        config=BenchmarkHarnessConfig(benchmark_id="bench-report-1"),
    )

    report = build_benchmark_report(
        harness_result,
        quality_signals_by_candidate={
            "balanced": (
                BenchmarkQualitySignal("rubric_accuracy", 0.8, "Preserved constraints"),
            ),
            "deep": (
                BenchmarkQualitySignal("rubric_accuracy", 0.9, "More complete tradeoff analysis"),
            ),
        },
    )

    assert report.candidates[0].candidate_id == "deep"
    assert report.candidates[0].raw_metrics.final_result == "succeeded"
    assert report.candidates[0].raw_metrics.latency_ms == 250
    assert report.candidates[0].raw_metrics.cost_usd == 0.01
    assert report.candidates[0].quality_signals[0].name == "rubric_accuracy"
    assert report.candidates[0].ranking_inputs["quality_signal_avg"] == 0.9
    assert "quality_signals_missing" not in report.candidates[0].comparison_notes


def test_benchmark_report_surfaces_missing_metrics_and_ties() -> None:
    workload = load_benchmark_workload_manifest().workloads[0]
    harness_result = run_benchmark_workload(
        workload,
        (
            BenchmarkCandidate(
                "docs-a",
                _route(workload, "openrouter", "openai/gpt-4o-mini", "economy"),
                FakeExecutor(lambda execution_input: _result_for_without_precise_cost(execution_input)),
            ),
            BenchmarkCandidate(
                "docs-b",
                _route(workload, "local", "local/llama3.1:8b", "local"),
                FakeExecutor(lambda execution_input: _result_for_without_precise_cost(execution_input)),
            ),
        ),
        config=BenchmarkHarnessConfig(benchmark_id="bench-report-2"),
    )

    report = build_benchmark_report(harness_result)

    assert "cost_unavailable" in report.candidates[0].comparison_notes
    assert "quality_signals_missing" in report.candidates[0].comparison_notes
    assert report.candidates[1].tied_with_previous is True
    assert "tied_on_ranking_inputs" in report.candidates[1].comparison_notes
    table = render_benchmark_report_table(report)
    assert "quality_avg" in table
    assert "cost_unavailable" in table


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


def _result_for_without_precise_cost(execution_input) -> ProviderExecutionResult:
    result = _result_for(execution_input, output_text="docs")
    usage = ProviderUsage(tokens_prompt=10, tokens_completion=5, total_tokens=15, latency_ms=250)
    summary = dict(result.attempt_summary)
    summary["usage"] = usage.as_schema_payload()
    summary["duration_ms"] = 250
    return ProviderExecutionResult(
        status=result.status,
        output_text=result.output_text,
        tool_calls=result.tool_calls,
        usage=usage,
        events=result.events,
        attempt_summary=summary,
        retry_count=result.retry_count,
        metadata=result.metadata,
    )