"""Normalized telemetry ingestion for adaptive dispatch scoring inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class AdaptiveTelemetryEntry:
    """Scoring-ready telemetry for one provider or model candidate."""

    provider: str
    model: str
    attempts_total: int
    succeeded_count: int
    failed_count: int
    blocked_count: int
    retry_count_total: int
    tool_call_count_total: int
    success_rate: float
    failure_rate: float
    blocked_rate: float
    avg_duration_ms: float | None
    avg_total_tokens: float | None
    avg_cost_usd: float | None
    freshness_seconds: int | None
    freshness_state: str
    telemetry_gaps: tuple[str, ...]
    source_kind: str
    last_observed_at: str | None = None


@dataclass(frozen=True, slots=True)
class AdaptiveTelemetrySnapshot:
    """Timestamped adaptive dispatch telemetry snapshot."""

    source_kind: str
    generated_at: str
    entries: tuple[AdaptiveTelemetryEntry, ...]


def build_adaptive_snapshot_from_attempt_summaries(
    attempt_summaries: Iterable[Mapping[str, Any]],
    *,
    generated_at: datetime | None = None,
    freshness_reference: datetime | None = None,
    stale_after: timedelta = timedelta(days=7),
) -> AdaptiveTelemetrySnapshot:
    """Build adaptive telemetry from normalized attempt summaries."""

    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for summary in attempt_summaries:
        provider = _optional_string(summary.get("provider")) or "unknown"
        model = _optional_string(summary.get("model")) or "unknown"
        grouped.setdefault((provider, model), []).append(summary)

    reference_time = freshness_reference or generated_at or datetime.now(UTC)
    built_entries = [
        _attempt_group_entry(
            provider=provider,
            model=model,
            summaries=summaries,
            freshness_reference=reference_time,
            stale_after=stale_after,
        )
        for (provider, model), summaries in sorted(grouped.items())
    ]
    generation_time = generated_at or datetime.now(UTC)
    return AdaptiveTelemetrySnapshot(
        source_kind="attempt_summaries",
        generated_at=_format_iso_datetime(generation_time),
        entries=tuple(built_entries),
    )


def build_adaptive_snapshot_from_aggregate_records(
    aggregate_records: Iterable[Mapping[str, Any]],
    *,
    generated_at: datetime | None = None,
    freshness_reference: datetime | None = None,
    stale_after: timedelta = timedelta(days=7),
) -> AdaptiveTelemetrySnapshot:
    """Build adaptive telemetry from normalized analytics aggregate records."""

    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in aggregate_records:
        dimensions = _as_mapping(record.get("dimensions"))
        provider = _optional_string(dimensions.get("provider")) or "unknown"
        model = _optional_string(dimensions.get("model")) or "unknown"
        grouped.setdefault((provider, model), []).append(record)

    reference_time = freshness_reference or generated_at or datetime.now(UTC)
    built_entries = [
        _aggregate_group_entry(
            provider=provider,
            model=model,
            records=records,
            freshness_reference=reference_time,
            stale_after=stale_after,
        )
        for (provider, model), records in sorted(grouped.items())
    ]
    generation_time = generated_at or datetime.now(UTC)
    return AdaptiveTelemetrySnapshot(
        source_kind="aggregate_records",
        generated_at=_format_iso_datetime(generation_time),
        entries=tuple(built_entries),
    )


def _attempt_group_entry(
    *,
    provider: str,
    model: str,
    summaries: list[Mapping[str, Any]],
    freshness_reference: datetime,
    stale_after: timedelta,
) -> AdaptiveTelemetryEntry:
    attempts_total = len(summaries)
    succeeded_count = sum(1 for summary in summaries if summary.get("final_result") == "succeeded")
    failed_count = sum(1 for summary in summaries if summary.get("final_result") == "failed")
    blocked_count = sum(1 for summary in summaries if summary.get("final_result") == "blocked")
    retry_count_total = sum(_int_or_zero(summary.get("retry_count")) for summary in summaries)
    tool_call_count_total = sum(_int_or_zero(summary.get("tool_call_count")) for summary in summaries)

    duration_values = [_summary_duration_ms(summary) for summary in summaries]
    total_token_values = [_summary_total_tokens(summary) for summary in summaries]
    cost_values = [_summary_cost_usd(summary) for summary in summaries]
    last_observed = max(
        (_summary_last_observed(summary) for summary in summaries if _summary_last_observed(summary)),
        default=None,
    )

    telemetry_gaps: list[str] = []
    if provider == "unknown":
        telemetry_gaps.append("provider_missing")
    if model == "unknown":
        telemetry_gaps.append("model_missing")

    avg_duration_ms = _average_numeric_values(duration_values, telemetry_gaps, "duration_ms")
    avg_total_tokens = _average_numeric_values(total_token_values, telemetry_gaps, "total_tokens")
    avg_cost_usd = _average_precise_cost(cost_values, telemetry_gaps)
    freshness_seconds, freshness_state = _freshness_state(
        last_observed,
        freshness_reference=freshness_reference,
        stale_after=stale_after,
        telemetry_gaps=telemetry_gaps,
    )

    return AdaptiveTelemetryEntry(
        provider=provider,
        model=model,
        attempts_total=attempts_total,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        blocked_count=blocked_count,
        retry_count_total=retry_count_total,
        tool_call_count_total=tool_call_count_total,
        success_rate=_safe_rate(succeeded_count, attempts_total),
        failure_rate=_safe_rate(failed_count, attempts_total),
        blocked_rate=_safe_rate(blocked_count, attempts_total),
        avg_duration_ms=avg_duration_ms,
        avg_total_tokens=avg_total_tokens,
        avg_cost_usd=avg_cost_usd,
        freshness_seconds=freshness_seconds,
        freshness_state=freshness_state,
        telemetry_gaps=tuple(sorted(set(telemetry_gaps))),
        source_kind="attempt_summaries",
        last_observed_at=_format_iso_datetime(last_observed) if last_observed is not None else None,
    )


def _aggregate_group_entry(
    *,
    provider: str,
    model: str,
    records: list[Mapping[str, Any]],
    freshness_reference: datetime,
    stale_after: timedelta,
) -> AdaptiveTelemetryEntry:
    telemetry_gaps: list[str] = []
    if provider == "unknown":
        telemetry_gaps.append("provider_missing")
    if model == "unknown":
        telemetry_gaps.append("model_missing")

    attempts_total = 0
    succeeded_count = 0
    failed_count = 0
    blocked_count = 0
    retry_count_total = 0
    tool_call_count_total = 0
    duration_ms_total = 0.0
    duration_denominator = 0
    total_tokens_total = 0.0
    tokens_denominator = 0
    cost_usd_total = 0.0
    last_observed: datetime | None = None

    for record in records:
        metrics = _as_mapping(record.get("metrics"))
        window = _as_mapping(record.get("window"))

        record_attempts = _int_or_zero(metrics.get("attempts_total"))
        attempts_total += record_attempts
        succeeded_count += _int_or_zero(metrics.get("succeeded_count"))
        failed_count += _int_or_zero(metrics.get("failed_count"))
        blocked_count += _int_or_zero(metrics.get("blocked_count"))
        retry_count_total += _int_or_zero(metrics.get("retry_count_total"))
        tool_call_count_total += _int_or_zero(metrics.get("tool_call_count_total"))

        if record_attempts > 0:
            duration_ms_total += _float_or_zero(metrics.get("duration_ms_total"))
            duration_denominator += record_attempts
            total_tokens_total += _float_or_zero(metrics.get("total_tokens_total"))
            tokens_denominator += record_attempts

        end_at = _parse_iso_datetime(_optional_string(window.get("end_at")))
        if end_at is not None and (last_observed is None or end_at > last_observed):
            last_observed = end_at

    if duration_denominator == 0:
        telemetry_gaps.append("duration_ms_unavailable")
        avg_duration_ms = None
    else:
        avg_duration_ms = duration_ms_total / duration_denominator

    if tokens_denominator == 0:
        telemetry_gaps.append("total_tokens_unavailable")
        avg_total_tokens = None
    else:
        avg_total_tokens = total_tokens_total / tokens_denominator

    avg_cost_usd = _aggregate_average_cost(
        provider=provider,
        records=records,
        attempts_total=attempts_total,
        telemetry_gaps=telemetry_gaps,
    )
    freshness_seconds, freshness_state = _freshness_state(
        last_observed,
        freshness_reference=freshness_reference,
        stale_after=stale_after,
        telemetry_gaps=telemetry_gaps,
    )

    return AdaptiveTelemetryEntry(
        provider=provider,
        model=model,
        attempts_total=attempts_total,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        blocked_count=blocked_count,
        retry_count_total=retry_count_total,
        tool_call_count_total=tool_call_count_total,
        success_rate=_safe_rate(succeeded_count, attempts_total),
        failure_rate=_safe_rate(failed_count, attempts_total),
        blocked_rate=_safe_rate(blocked_count, attempts_total),
        avg_duration_ms=avg_duration_ms,
        avg_total_tokens=avg_total_tokens,
        avg_cost_usd=avg_cost_usd,
        freshness_seconds=freshness_seconds,
        freshness_state=freshness_state,
        telemetry_gaps=tuple(sorted(set(telemetry_gaps))),
        source_kind="aggregate_records",
        last_observed_at=_format_iso_datetime(last_observed) if last_observed is not None else None,
    )


def _summary_duration_ms(summary: Mapping[str, Any]) -> int | None:
    duration_ms = summary.get("duration_ms")
    if isinstance(duration_ms, int):
        return duration_ms
    usage = _as_mapping(summary.get("usage"))
    latency_ms = usage.get("latency_ms")
    if isinstance(latency_ms, int):
        return latency_ms
    return None


def _summary_total_tokens(summary: Mapping[str, Any]) -> int | None:
    usage = _as_mapping(summary.get("usage"))
    total_tokens = usage.get("total_tokens")
    if isinstance(total_tokens, int):
        return total_tokens
    return None


def _summary_cost_usd(summary: Mapping[str, Any]) -> float | None:
    usage = _as_mapping(summary.get("usage"))
    cost_usd = usage.get("cost_usd")
    if isinstance(cost_usd, int | float):
        return float(cost_usd)
    return None


def _summary_last_observed(summary: Mapping[str, Any]) -> datetime | None:
    ended_at = _parse_iso_datetime(_optional_string(summary.get("ended_at")))
    if ended_at is not None:
        return ended_at
    return _parse_iso_datetime(_optional_string(summary.get("started_at")))


def _average_numeric_values(
    values: list[int | None],
    telemetry_gaps: list[str],
    gap_prefix: str,
) -> float | None:
    known_values = [value for value in values if value is not None]
    if not known_values:
        telemetry_gaps.append(f"{gap_prefix}_unavailable")
        return None
    if len(known_values) != len(values):
        telemetry_gaps.append(f"{gap_prefix}_partial")
    return sum(known_values) / len(known_values)


def _average_precise_cost(values: list[float | None], telemetry_gaps: list[str]) -> float | None:
    known_values = [value for value in values if value is not None]
    if not known_values:
        telemetry_gaps.append("cost_usd_unavailable")
        return None
    if len(known_values) != len(values):
        telemetry_gaps.append("cost_usd_partial")
        return None
    return sum(known_values) / len(known_values)


def _aggregate_average_cost(
    *,
    provider: str,
    records: list[Mapping[str, Any]],
    attempts_total: int,
    telemetry_gaps: list[str],
) -> float | None:
    if attempts_total <= 0:
        telemetry_gaps.append("cost_usd_unavailable")
        return None

    total_cost = sum(_float_or_zero(_as_mapping(record.get("metrics")).get("cost_usd_total")) for record in records)
    if provider == "local":
        telemetry_gaps.append("cost_precision_unknown_from_aggregate")
        return None
    return total_cost / attempts_total


def _freshness_state(
    last_observed: datetime | None,
    *,
    freshness_reference: datetime,
    stale_after: timedelta,
    telemetry_gaps: list[str],
) -> tuple[int | None, str]:
    if last_observed is None:
        telemetry_gaps.append("freshness_unknown")
        return None, "unknown"

    age_seconds = max(int((freshness_reference - last_observed).total_seconds()), 0)
    if freshness_reference - last_observed > stale_after:
        telemetry_gaps.append("stale_telemetry")
        return age_seconds, "stale"
    return age_seconds, "fresh"


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
    if isinstance(value, int | float):
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