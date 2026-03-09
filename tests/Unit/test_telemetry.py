"""Unit tests for adaptive telemetry snapshot building."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from higgs_agent.adaptive.telemetry import (
    build_adaptive_snapshot_from_aggregate_records,
    build_adaptive_snapshot_from_attempt_summaries,
)


def _attempt(
    provider: str = "openrouter",
    model: str = "test-model",
    result: str = "succeeded",
    **extra: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "provider": provider,
        "model": model,
        "final_result": result,
        "retry_count": 0,
        "tool_call_count": 0,
        "ended_at": "2026-01-15T10:00:00Z",
    }
    base.update(extra)
    return base


def test_snapshot_from_single_attempt() -> None:
    snap = build_adaptive_snapshot_from_attempt_summaries(
        [_attempt()],
        generated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )
    assert snap.source_kind == "attempt_summaries"
    assert len(snap.entries) == 1
    entry = snap.entries[0]
    assert entry.provider == "openrouter"
    assert entry.model == "test-model"
    assert entry.attempts_total == 1
    assert entry.succeeded_count == 1
    assert entry.success_rate == 1.0


def test_snapshot_groups_by_provider_model() -> None:
    snap = build_adaptive_snapshot_from_attempt_summaries(
        [
            _attempt(provider="a", model="m1"),
            _attempt(provider="a", model="m2"),
            _attempt(provider="b", model="m1"),
        ],
        generated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )
    assert len(snap.entries) == 3
    keys = [(e.provider, e.model) for e in snap.entries]
    assert keys == [("a", "m1"), ("a", "m2"), ("b", "m1")]


def test_snapshot_computes_failure_rate() -> None:
    snap = build_adaptive_snapshot_from_attempt_summaries(
        [
            _attempt(result="succeeded"),
            _attempt(result="failed"),
            _attempt(result="failed"),
            _attempt(result="blocked"),
        ],
        generated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )
    entry = snap.entries[0]
    assert entry.attempts_total == 4
    assert entry.failure_rate == 0.5
    assert entry.blocked_rate == 0.25


def test_snapshot_detects_missing_provider_gap() -> None:
    snap = build_adaptive_snapshot_from_attempt_summaries(
        [_attempt(provider=None)],
        generated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )
    entry = snap.entries[0]
    assert entry.provider == "unknown"
    assert "provider_missing" in entry.telemetry_gaps


def test_snapshot_detects_stale_telemetry() -> None:
    old_time = "2025-01-01T00:00:00Z"
    snap = build_adaptive_snapshot_from_attempt_summaries(
        [_attempt(ended_at=old_time)],
        generated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        freshness_reference=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        stale_after=timedelta(days=7),
    )
    entry = snap.entries[0]
    assert entry.freshness_state == "stale"
    assert "stale_telemetry" in entry.telemetry_gaps


def test_snapshot_duration_gap_when_unavailable() -> None:
    snap = build_adaptive_snapshot_from_attempt_summaries(
        [_attempt()],
        generated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )
    entry = snap.entries[0]
    assert entry.avg_duration_ms is None
    assert "duration_ms_unavailable" in entry.telemetry_gaps


def test_snapshot_from_aggregate_records() -> None:
    records = [
        {
            "dimensions": {"provider": "openrouter", "model": "test-model"},
            "metrics": {
                "attempts_total": 10,
                "succeeded_count": 8,
                "failed_count": 2,
                "blocked_count": 0,
                "retry_count_total": 1,
                "tool_call_count_total": 5,
                "duration_ms_total": 5000.0,
                "total_tokens_total": 10000.0,
                "cost_usd_total": 0.50,
            },
            "window": {
                "end_at": "2026-01-15T10:00:00Z",
            },
        }
    ]
    snap = build_adaptive_snapshot_from_aggregate_records(
        records,
        generated_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )
    assert snap.source_kind == "aggregate_records"
    assert len(snap.entries) == 1
    entry = snap.entries[0]
    assert entry.attempts_total == 10
    assert entry.succeeded_count == 8
    assert entry.avg_duration_ms == 500.0
    assert entry.avg_total_tokens == 1000.0
    assert entry.avg_cost_usd == 0.05
