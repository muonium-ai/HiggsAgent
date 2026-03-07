"""Benchmark ranking and quality reporting outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .harness import BenchmarkCandidateResult, BenchmarkHarnessResult


@dataclass(frozen=True, slots=True)
class BenchmarkQualitySignal:
    """Explicit reviewable quality signal attached to one benchmark candidate."""

    name: str
    score: float
    rationale: str


@dataclass(frozen=True, slots=True)
class BenchmarkRawMetrics:
    """Raw normalized metrics derived from benchmark execution outputs."""

    status: str
    final_result: str
    retry_count: int
    tool_call_count: int
    latency_ms: int | None
    total_tokens: int | None
    cost_usd: float | None
    has_precise_cost: bool


@dataclass(frozen=True, slots=True)
class BenchmarkCandidateReport:
    """Reviewable comparison record for one benchmark candidate."""

    candidate_id: str
    provider: str | None
    model_id: str | None
    route_family: str | None
    raw_metrics: BenchmarkRawMetrics
    quality_signals: tuple[BenchmarkQualitySignal, ...]
    ranking_inputs: dict[str, float | int | None]
    comparison_notes: tuple[str, ...]
    rank_position: int
    tied_with_previous: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "provider": self.provider,
            "model_id": self.model_id,
            "route_family": self.route_family,
            "raw_metrics": {
                "status": self.raw_metrics.status,
                "final_result": self.raw_metrics.final_result,
                "retry_count": self.raw_metrics.retry_count,
                "tool_call_count": self.raw_metrics.tool_call_count,
                "latency_ms": self.raw_metrics.latency_ms,
                "total_tokens": self.raw_metrics.total_tokens,
                "cost_usd": self.raw_metrics.cost_usd,
                "has_precise_cost": self.raw_metrics.has_precise_cost,
            },
            "quality_signals": [
                {"name": signal.name, "score": signal.score, "rationale": signal.rationale}
                for signal in self.quality_signals
            ],
            "ranking_inputs": dict(self.ranking_inputs),
            "comparison_notes": list(self.comparison_notes),
            "rank_position": self.rank_position,
            "tied_with_previous": self.tied_with_previous,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Full benchmark report with explainable ranking outputs."""

    benchmark_id: str
    workload_id: str
    ranking_policy: tuple[str, ...]
    candidates: tuple[BenchmarkCandidateReport, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "benchmark_id": self.benchmark_id,
            "workload_id": self.workload_id,
            "ranking_policy": list(self.ranking_policy),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


def build_benchmark_report(
    harness_result: BenchmarkHarnessResult,
    *,
    quality_signals_by_candidate: Mapping[str, Iterable[BenchmarkQualitySignal]] | None = None,
) -> BenchmarkReport:
    """Build a reviewable benchmark report from normalized harness outputs."""

    quality_signal_index = {
        candidate_id: tuple(signals)
        for candidate_id, signals in (quality_signals_by_candidate or {}).items()
    }

    ranked_candidates = sorted(
        (
            _candidate_report(
                candidate_result,
                quality_signal_index.get(candidate_result.candidate_id, ()),
            )
            for candidate_result in harness_result.candidate_results
        ),
        key=_ranking_key,
    )

    candidate_reports: list[BenchmarkCandidateReport] = []
    previous_tie_key: tuple[object, ...] | None = None
    for index, candidate in enumerate(ranked_candidates, start=1):
        current_tie_key = _tie_key(candidate)
        notes = list(candidate.comparison_notes)
        tied_with_previous = previous_tie_key == current_tie_key
        if tied_with_previous:
            notes.append("tied_on_ranking_inputs")
        candidate_reports.append(
            BenchmarkCandidateReport(
                candidate_id=candidate.candidate_id,
                provider=candidate.provider,
                model_id=candidate.model_id,
                route_family=candidate.route_family,
                raw_metrics=candidate.raw_metrics,
                quality_signals=candidate.quality_signals,
                ranking_inputs=candidate.ranking_inputs,
                comparison_notes=tuple(notes),
                rank_position=index,
                tied_with_previous=tied_with_previous,
            )
        )
        previous_tie_key = current_tie_key

    return BenchmarkReport(
        benchmark_id=harness_result.benchmark_id,
        workload_id=harness_result.workload.workload_id,
        ranking_policy=(
            "final_result_desc",
            "quality_signal_avg_desc",
            "latency_ms_asc",
            "retry_count_asc",
            "precise_cost_usd_asc",
            "candidate_id_asc",
        ),
        candidates=tuple(candidate_reports),
    )


def render_benchmark_report_table(report: BenchmarkReport) -> str:
    """Render benchmark results into a compact comparison table."""

    if not report.candidates:
        return "No benchmark candidates were executed."

    headers = [
        "rank",
        "candidate",
        "provider",
        "model",
        "result",
        "quality_avg",
        "latency_ms",
        "retry_count",
        "cost_usd",
        "notes",
    ]
    rows = [headers]
    for candidate in report.candidates:
        rows.append(
            [
                _rank_label(candidate.rank_position, candidate.tied_with_previous),
                candidate.candidate_id,
                candidate.provider or "unknown",
                candidate.model_id or "unknown",
                candidate.raw_metrics.final_result,
                _format_optional_float(candidate.ranking_inputs.get("quality_signal_avg")),
                _format_optional_int(candidate.raw_metrics.latency_ms),
                str(candidate.raw_metrics.retry_count),
                _format_optional_float(candidate.raw_metrics.cost_usd, precision=4),
                ",".join(candidate.comparison_notes) or "-",
            ]
        )

    widths = [max(len(row[index]) for row in rows) for index in range(len(headers))]
    return "\n".join(
        " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)) for row in rows
    )


def _candidate_report(
    candidate_result: BenchmarkCandidateResult,
    quality_signals: tuple[BenchmarkQualitySignal, ...],
) -> BenchmarkCandidateReport:
    summary = candidate_result.execution_result.attempt_summary
    usage = summary.get("usage") if isinstance(summary.get("usage"), dict) else {}
    status = candidate_result.execution_result.status
    final_result = str(summary.get("final_result", status))
    retry_count = int(summary.get("retry_count", 0))
    tool_call_count = int(summary.get("tool_call_count", 0))

    latency_ms: int | None = None
    usage_latency = usage.get("latency_ms")
    if isinstance(usage_latency, int):
        latency_ms = usage_latency
    else:
        duration_ms = summary.get("duration_ms")
        if isinstance(duration_ms, int):
            latency_ms = duration_ms

    total_tokens = usage.get("total_tokens") if isinstance(usage.get("total_tokens"), int) else None
    cost_usd = None
    usage_cost = usage.get("cost_usd")
    if isinstance(usage_cost, int | float):
        cost_usd = float(usage_cost)
    has_precise_cost = cost_usd is not None
    quality_signal_avg = _quality_signal_average(quality_signals)

    notes: list[str] = []
    if latency_ms is None:
        notes.append("latency_unavailable")
    if not has_precise_cost:
        notes.append("cost_unavailable")
    if not quality_signals:
        notes.append("quality_signals_missing")
    if final_result != "succeeded":
        notes.append(f"non_success_result:{final_result}")

    raw_metrics = BenchmarkRawMetrics(
        status=status,
        final_result=final_result,
        retry_count=retry_count,
        tool_call_count=tool_call_count,
        latency_ms=latency_ms,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        has_precise_cost=has_precise_cost,
    )
    return BenchmarkCandidateReport(
        candidate_id=candidate_result.candidate_id,
        provider=candidate_result.route.provider,
        model_id=candidate_result.route.model_id,
        route_family=candidate_result.route.route_family,
        raw_metrics=raw_metrics,
        quality_signals=quality_signals,
        ranking_inputs={
            "final_result_rank": _final_result_rank(final_result),
            "quality_signal_avg": quality_signal_avg,
            "latency_ms": latency_ms,
            "retry_count": retry_count,
            "cost_usd": cost_usd,
        },
        comparison_notes=tuple(notes),
        rank_position=0,
        tied_with_previous=False,
    )


def _ranking_key(candidate: BenchmarkCandidateReport) -> tuple[object, ...]:
    return (*_tie_key(candidate), candidate.candidate_id)


def _tie_key(candidate: BenchmarkCandidateReport) -> tuple[object, ...]:
    quality_signal_avg = candidate.ranking_inputs.get("quality_signal_avg")
    latency_ms = candidate.raw_metrics.latency_ms if candidate.raw_metrics.latency_ms is not None else 999999999
    cost_usd = candidate.raw_metrics.cost_usd if candidate.raw_metrics.cost_usd is not None else 999999999.0
    return (
        -int(candidate.ranking_inputs["final_result_rank"]),
        -(float(quality_signal_avg) if quality_signal_avg is not None else -1.0),
        latency_ms,
        candidate.raw_metrics.retry_count,
        cost_usd,
    )


def _quality_signal_average(quality_signals: tuple[BenchmarkQualitySignal, ...]) -> float | None:
    if not quality_signals:
        return None
    return round(sum(signal.score for signal in quality_signals) / len(quality_signals), 6)


def _final_result_rank(final_result: str) -> int:
    return {
        "succeeded": 4,
        "skipped": 3,
        "failed": 2,
        "blocked": 1,
    }.get(final_result, 0)


def _format_optional_float(value: object, *, precision: int = 2) -> str:
    if isinstance(value, int | float):
        return f"{float(value):.{precision}f}"
    return "-"


def _format_optional_int(value: int | None) -> str:
    if value is None:
        return "-"
    return str(value)


def _rank_label(rank_position: int, tied_with_previous: bool) -> str:
    if tied_with_previous:
        return f"={rank_position}"
    return str(rank_position)