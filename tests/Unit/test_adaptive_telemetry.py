from __future__ import annotations

from datetime import UTC, datetime, timedelta

from higgs_agent.adaptive import (
    build_adaptive_snapshot_from_aggregate_records,
    build_adaptive_snapshot_from_attempt_summaries,
)


def test_attempt_summary_snapshot_preserves_partial_local_metrics() -> None:
    snapshot = build_adaptive_snapshot_from_attempt_summaries(
        (
            {
                "ticket_id": "T-local-1",
                "provider": "local",
                "model": "local/llama3.1:8b",
                "final_result": "succeeded",
                "retry_count": 0,
                "tool_call_count": 0,
                "ended_at": "2026-03-07T10:00:00Z",
                "usage": {"total_tokens": 48, "latency_ms": 1200},
            },
            {
                "ticket_id": "T-hosted-1",
                "provider": "openrouter",
                "model": "openai/gpt-4o",
                "final_result": "failed",
                "retry_count": 1,
                "tool_call_count": 2,
                "ended_at": "2026-03-07T10:01:00Z",
                "duration_ms": 2000,
                "usage": {"total_tokens": 100, "cost_usd": 0.2},
            },
        ),
        generated_at=datetime(2026, 3, 7, 10, 5, tzinfo=UTC),
        freshness_reference=datetime(2026, 3, 7, 10, 5, tzinfo=UTC),
    )

    local_entry = next(entry for entry in snapshot.entries if entry.provider == "local")
    hosted_entry = next(entry for entry in snapshot.entries if entry.provider == "openrouter")

    assert snapshot.source_kind == "attempt_summaries"
    assert local_entry.attempts_total == 1
    assert local_entry.avg_total_tokens == 48
    assert local_entry.avg_cost_usd is None
    assert local_entry.freshness_state == "fresh"
    assert "cost_usd_unavailable" in local_entry.telemetry_gaps

    assert hosted_entry.failed_count == 1
    assert hosted_entry.retry_count_total == 1
    assert hosted_entry.avg_cost_usd == 0.2


def test_attempt_summary_snapshot_flags_stale_and_missing_telemetry() -> None:
    snapshot = build_adaptive_snapshot_from_attempt_summaries(
        (
            {
                "ticket_id": "T-unknown-1",
                "final_result": "succeeded",
                "retry_count": 0,
                "tool_call_count": 0,
                "started_at": "2026-02-20T10:00:00Z",
            },
        ),
        freshness_reference=datetime(2026, 3, 7, 10, 0, tzinfo=UTC),
        stale_after=timedelta(days=3),
    )

    entry = snapshot.entries[0]

    assert entry.provider == "unknown"
    assert entry.model == "unknown"
    assert entry.freshness_state == "stale"
    assert "provider_missing" in entry.telemetry_gaps
    assert "model_missing" in entry.telemetry_gaps
    assert "duration_ms_unavailable" in entry.telemetry_gaps
    assert "total_tokens_unavailable" in entry.telemetry_gaps
    assert "cost_usd_unavailable" in entry.telemetry_gaps
    assert "stale_telemetry" in entry.telemetry_gaps


def test_aggregate_snapshot_merges_provider_model_records_and_marks_local_cost_precision_gap() -> None:
    snapshot = build_adaptive_snapshot_from_aggregate_records(
        (
            {
                "dimensions": {"provider": "openrouter", "model": "openai/gpt-4o"},
                "window": {"end_at": "2026-03-07T11:00:00Z"},
                "metrics": {
                    "attempts_total": 2,
                    "succeeded_count": 1,
                    "failed_count": 1,
                    "blocked_count": 0,
                    "retry_count_total": 1,
                    "tool_call_count_total": 2,
                    "duration_ms_total": 3000,
                    "total_tokens_total": 150,
                    "cost_usd_total": 0.3,
                },
            },
            {
                "dimensions": {"provider": "openrouter", "model": "openai/gpt-4o"},
                "window": {"end_at": "2026-03-07T12:00:00Z"},
                "metrics": {
                    "attempts_total": 1,
                    "succeeded_count": 1,
                    "failed_count": 0,
                    "blocked_count": 0,
                    "retry_count_total": 0,
                    "tool_call_count_total": 1,
                    "duration_ms_total": 900,
                    "total_tokens_total": 60,
                    "cost_usd_total": 0.12,
                },
            },
            {
                "dimensions": {"provider": "local", "model": "local/llama3.1:8b"},
                "window": {"end_at": "2026-03-07T12:30:00Z"},
                "metrics": {
                    "attempts_total": 2,
                    "succeeded_count": 2,
                    "failed_count": 0,
                    "blocked_count": 0,
                    "retry_count_total": 0,
                    "tool_call_count_total": 0,
                    "duration_ms_total": 1800,
                    "total_tokens_total": 70,
                    "cost_usd_total": 0.0,
                },
            },
        ),
        freshness_reference=datetime(2026, 3, 7, 13, 0, tzinfo=UTC),
    )

    hosted_entry = next(entry for entry in snapshot.entries if entry.provider == "openrouter")
    local_entry = next(entry for entry in snapshot.entries if entry.provider == "local")

    assert snapshot.source_kind == "aggregate_records"
    assert hosted_entry.attempts_total == 3
    assert round(hosted_entry.avg_duration_ms or 0.0, 2) == 1300.0
    assert round(hosted_entry.avg_total_tokens or 0.0, 2) == 70.0
    assert round(hosted_entry.avg_cost_usd or 0.0, 2) == 0.14
    assert hosted_entry.freshness_state == "fresh"

    assert local_entry.attempts_total == 2
    assert local_entry.avg_cost_usd is None
    assert "cost_precision_unknown_from_aggregate" in local_entry.telemetry_gaps