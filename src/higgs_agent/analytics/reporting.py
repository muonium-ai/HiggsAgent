"""Local analytics aggregation and reporting surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from higgs_agent.routing import ClassificationInputError, classify_ticket
from higgs_agent.tickets import TicketRecord

GROUP_DIMENSIONS = {
    "provider",
    "model",
    "ticket_type",
    "ticket_priority",
    "higgs_platform",
    "higgs_complexity",
    "final_result",
    "error_kind",
}

SENSITIVE_FIELD_NAMES = {
    "api_key",
    "authorization",
    "bearer_token",
    "cookie",
    "env",
    "headers",
    "private_key",
    "prompt",
    "provider_headers",
    "provider_payload",
    "raw_prompt",
    "raw_response",
    "response",
    "secret",
    "stderr",
    "stdout",
    "token",
    "tool_stderr",
    "tool_stdout",
}


@dataclass(frozen=True, slots=True)
class AnalyticsFilter:
    """Filter and grouping options for analytics aggregation."""

    provider: str | None = None
    model: str | None = None
    ticket_type: str | None = None
    ticket_priority: str | None = None
    higgs_platform: str | None = None
    higgs_complexity: str | None = None
    final_result: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    group_by: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalyticsReport:
    """Aggregated analytics report result."""

    records: tuple[dict[str, object], ...]

    def to_json(self) -> str:
        return json.dumps(list(self.records), indent=2, sort_keys=True)


def load_attempt_summaries(path: Path) -> tuple[dict[str, Any], ...]:
    """Load newline-delimited attempt summary records from local analytics storage."""

    if not path.exists():
        raise FileNotFoundError(f"attempt summaries file not found: {path}")

    records: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"attempt summary line is not an object: {line!r}")
        records.append(payload)
    return tuple(records)


def build_ticket_metadata_index(tickets_dir: Path) -> dict[str, dict[str, str]]:
    """Build a metadata index for active and archived tickets used in analytics grouping."""

    ticket_paths = sorted(tickets_dir.glob("T-*.md"))
    archive_dir = tickets_dir / "archive"
    if archive_dir.is_dir():
        ticket_paths.extend(sorted(archive_dir.glob("T-*.md")))

    metadata_index: dict[str, dict[str, str]] = {}
    for path in ticket_paths:
        record = TicketRecord.from_path(path)
        frontmatter = record.frontmatter
        metadata = {
            "ticket_type": _optional_string(frontmatter.get("type")),
            "ticket_priority": _optional_string(frontmatter.get("priority")) or "p2",
            "higgs_platform": "agnostic",
            "higgs_complexity": "medium",
        }
        try:
            semantics = classify_ticket(record)
        except ClassificationInputError:
            pass
        else:
            metadata["higgs_platform"] = semantics.platform
            metadata["higgs_complexity"] = semantics.complexity
        metadata_index[record.id] = metadata

    return metadata_index


def aggregate_attempt_summaries(
    attempt_summaries: Iterable[Mapping[str, Any]],
    ticket_metadata_index: Mapping[str, Mapping[str, str]],
    analytics_filter: AnalyticsFilter,
    *,
    generated_at: datetime | None = None,
) -> AnalyticsReport:
    """Aggregate attempt summaries into Phase 2 analytics records."""

    for dimension in analytics_filter.group_by:
        if dimension not in GROUP_DIMENSIONS:
            raise ValueError(f"unsupported group_by dimension: {dimension}")

    filtered_rows: list[dict[str, Any]] = []
    for summary in attempt_summaries:
        row = _enrich_summary(summary, ticket_metadata_index)
        if _matches_filter(row, analytics_filter):
            filtered_rows.append(row)

    if not filtered_rows:
        return AnalyticsReport(records=())

    groups: dict[tuple[tuple[str, str], ...], list[dict[str, Any]]] = {}
    for row in filtered_rows:
        group_key = tuple(
            (dimension, str(row.get(dimension, ""))) for dimension in analytics_filter.group_by
        )
        groups.setdefault(group_key, []).append(row)

    built_records = [
        _build_aggregate_record(group_key, rows, analytics_filter, generated_at)
        for group_key, rows in sorted(groups.items())
    ]
    return AnalyticsReport(records=tuple(built_records))


def render_report_table(report: AnalyticsReport) -> str:
    """Render analytics report records into a compact operator-facing table."""

    if not report.records:
        return "No analytics records matched the selected filters."

    first = report.records[0]
    dimensions = list(_dimension_keys(first.get("dimensions", {})))
    headers = dimensions + [
        "attempts",
        "success_rate",
        "failure_rate",
        "cost_total_usd",
        "duration_avg_ms",
        "retries_total",
        "tool_calls_total",
    ]

    rows: list[list[str]] = [headers]
    for record in report.records:
        metrics = _as_mapping(record["metrics"])
        dimension_values = _as_mapping(record.get("dimensions", {}))
        rows.append(
            [str(dimension_values.get(name, "all")) for name in dimensions]
            + [
                str(metrics["attempts_total"]),
                f"{float(metrics['success_rate']):.2f}",
                f"{float(metrics['failure_rate']):.2f}",
                f"{float(metrics['cost_usd_total']):.4f}",
                f"{float(metrics['duration_ms_avg']):.1f}",
                str(metrics["retry_count_total"]),
                str(metrics["tool_call_count_total"]),
            ]
        )

    widths = [max(len(row[index]) for row in rows) for index in range(len(headers))]
    return "\n".join(
        " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)) for row in rows
    )


def _enrich_summary(
    summary: Mapping[str, Any], ticket_metadata_index: Mapping[str, Mapping[str, str]]
) -> dict[str, Any]:
    ticket_id = _optional_string(summary.get("ticket_id")) or ""
    ticket_metadata = ticket_metadata_index.get(ticket_id, {})
    usage = _as_mapping(summary.get("usage", {}))
    error = _as_mapping(summary.get("error", {}))

    duration_ms = summary.get("duration_ms")
    if not isinstance(duration_ms, int):
        latency_ms = usage.get("latency_ms")
        duration_ms = latency_ms if isinstance(latency_ms, int) else 0

    return {
        "ticket_id": ticket_id,
        "provider": _optional_string(summary.get("provider")),
        "model": _optional_string(summary.get("model")),
        "ticket_type": ticket_metadata.get("ticket_type"),
        "ticket_priority": ticket_metadata.get("ticket_priority", "p2"),
        "higgs_platform": ticket_metadata.get("higgs_platform", "agnostic"),
        "higgs_complexity": ticket_metadata.get("higgs_complexity", "medium"),
        "final_result": _optional_string(summary.get("final_result")),
        "error_kind": _optional_string(error.get("kind")),
        "started_at": _parse_iso_datetime(_optional_string(summary.get("started_at"))),
        "ended_at": _parse_iso_datetime(_optional_string(summary.get("ended_at"))),
        "tool_call_count": _int_or_zero(summary.get("tool_call_count")),
        "retry_count": _int_or_zero(summary.get("retry_count")),
        "duration_ms": duration_ms,
        "tokens_prompt": _int_or_zero(usage.get("tokens_prompt")),
        "tokens_completion": _int_or_zero(usage.get("tokens_completion")),
        "total_tokens": _int_or_zero(usage.get("total_tokens")),
        "cost_usd": _float_or_zero(usage.get("cost_usd")),
        "contains_sensitive_data": _contains_sensitive_analytics_input(summary),
    }


def _matches_filter(row: Mapping[str, Any], analytics_filter: AnalyticsFilter) -> bool:
    for key in (
        "provider",
        "model",
        "ticket_type",
        "ticket_priority",
        "higgs_platform",
        "higgs_complexity",
        "final_result",
    ):
        expected = getattr(analytics_filter, key)
        if expected is not None and row.get(key) != expected:
            return False

    started_at = row.get("started_at")
    if analytics_filter.start_at is not None:
        if not isinstance(started_at, datetime):
            return False
        if started_at < analytics_filter.start_at:
            return False

    ended_at = row.get("ended_at")
    if analytics_filter.end_at is not None:
        if not isinstance(ended_at, datetime):
            return False
        if ended_at > analytics_filter.end_at:
            return False

    return True


def _build_aggregate_record(
    group_key: tuple[tuple[str, str], ...],
    rows: list[dict[str, Any]],
    analytics_filter: AnalyticsFilter,
    generated_at: datetime | None,
) -> dict[str, object]:
    attempts_total = len(rows)
    succeeded_count = sum(1 for row in rows if row["final_result"] == "succeeded")
    failed_count = sum(1 for row in rows if row["final_result"] == "failed")
    blocked_count = sum(1 for row in rows if row["final_result"] == "blocked")
    skipped_count = sum(1 for row in rows if row["final_result"] == "skipped")
    retry_count_total = sum(int(row["retry_count"]) for row in rows)
    tool_call_count_total = sum(int(row["tool_call_count"]) for row in rows)
    duration_ms_total = sum(int(row["duration_ms"]) for row in rows)
    tokens_prompt_total = sum(int(row["tokens_prompt"]) for row in rows)
    tokens_completion_total = sum(int(row["tokens_completion"]) for row in rows)
    total_tokens_total = sum(int(row["total_tokens"]) for row in rows)
    cost_usd_total = sum(float(row["cost_usd"]) for row in rows)
    export_safe = not any(bool(row["contains_sensitive_data"]) for row in rows)

    dimensions = {key: value for key, value in group_key}
    started_at_values = [
        row["started_at"] for row in rows if isinstance(row["started_at"], datetime)
    ]
    ended_at_values = [row["ended_at"] for row in rows if isinstance(row["ended_at"], datetime)]
    earliest_start = min(started_at_values) if started_at_values else datetime.now(UTC)
    latest_end = max(ended_at_values) if ended_at_values else earliest_start
    generated_time = generated_at or datetime.now(UTC)

    return {
        "schema_version": 1,
        "aggregate_id": _build_aggregate_id(dimensions, earliest_start, latest_end),
        "generated_at": _format_iso_datetime(generated_time),
        "window": {
            "start_at": _format_iso_datetime(analytics_filter.start_at or earliest_start),
            "end_at": _format_iso_datetime(analytics_filter.end_at or latest_end),
            "granularity": _infer_granularity(analytics_filter),
        },
        "group_by": list(analytics_filter.group_by),
        "dimensions": dimensions,
        "source": {
            "attempt_summary_count": attempts_total,
            "event_count": 0,
            "used_event_backfill": False,
            "export_safe": export_safe,
        },
        "metrics": {
            "attempts_total": attempts_total,
            "distinct_ticket_count": len({row["ticket_id"] for row in rows}),
            "succeeded_count": succeeded_count,
            "failed_count": failed_count,
            "blocked_count": blocked_count,
            "skipped_count": skipped_count,
            "success_rate": _safe_rate(succeeded_count, attempts_total),
            "failure_rate": _safe_rate(failed_count, attempts_total),
            "blocked_rate": _safe_rate(blocked_count, attempts_total),
            "skipped_rate": _safe_rate(skipped_count, attempts_total),
            "retried_attempt_count": sum(1 for row in rows if int(row["retry_count"]) > 0),
            "retry_count_total": retry_count_total,
            "tool_call_count_total": tool_call_count_total,
            "tool_call_count_avg": tool_call_count_total / attempts_total,
            "duration_ms_total": duration_ms_total,
            "duration_ms_avg": duration_ms_total / attempts_total,
            "tokens_prompt_total": tokens_prompt_total,
            "tokens_completion_total": tokens_completion_total,
            "total_tokens_total": total_tokens_total,
            "cost_usd_total": round(cost_usd_total, 6),
            "cost_usd_avg": round(cost_usd_total / attempts_total, 6),
            "error_kind_counts": {
                "provider": sum(1 for row in rows if row["error_kind"] == "provider"),
                "tool": sum(1 for row in rows if row["error_kind"] == "tool"),
                "validation": sum(1 for row in rows if row["error_kind"] == "validation"),
                "guardrail": sum(1 for row in rows if row["error_kind"] == "guardrail"),
                "timeout": sum(1 for row in rows if row["error_kind"] == "timeout"),
                "internal": sum(1 for row in rows if row["error_kind"] == "internal"),
                "coordination": sum(1 for row in rows if row["error_kind"] == "coordination"),
            },
        },
    }


def _infer_granularity(analytics_filter: AnalyticsFilter) -> str:
    if analytics_filter.start_at is None and analytics_filter.end_at is None:
        return "all"
    return "custom"


def _build_aggregate_id(dimensions: Mapping[str, str], start_at: datetime, end_at: datetime) -> str:
    dimension_part = "-".join(f"{key}-{value}" for key, value in dimensions.items()) or "all"
    return f"agg-{start_at.date().isoformat()}-{end_at.date().isoformat()}-{dimension_part}"


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _format_iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) else 0


def _float_or_zero(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _dimension_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ()
    return tuple(str(key) for key in value.keys())


def _contains_sensitive_analytics_input(value: object, *, field_name: str | None = None) -> bool:
    if field_name is not None and field_name.lower() in SENSITIVE_FIELD_NAMES:
        return True

    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if _contains_sensitive_analytics_input(nested_value, field_name=str(key)):
                return True
        return False

    if isinstance(value, list):
        return any(_contains_sensitive_analytics_input(item) for item in value)

    if isinstance(value, str):
        lowered = value.lower()
        return (
            "sk-" in lowered
            or "bearer " in lowered
            or "-----begin" in lowered
            or "authorization:" in lowered
        )

    return False