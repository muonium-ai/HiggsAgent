"""Unit tests for event stream and attempt summary builders."""

from __future__ import annotations

import re

from higgs_agent.events.records import (
    AttemptSummaryBuilder,
    EventStreamBuilder,
    utc_now_iso,
)
from higgs_agent.providers.contract import (
    ExecutorArtifactRef,
    ExecutorLimits,
    ProviderUsage,
)

_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_utc_now_iso_format() -> None:
    result = utc_now_iso()
    assert _ISO_PATTERN.match(result), f"unexpected format: {result}"


def test_event_stream_builder_appends_events() -> None:
    builder = EventStreamBuilder(
        run_id="r1",
        attempt_id="a1",
        ticket_id="T-001",
        executor_version="test",
    )
    event = builder.append("execution.created", "started")
    assert event["event_type"] == "execution.created"
    assert event["status"] == "started"
    assert event["sequence"] == 0
    assert event["run_id"] == "r1"
    assert event["schema_version"] == 1
    assert "event_id" in event

    builder.append("execution.completed", "completed")
    events = builder.build()
    assert len(events) == 2
    assert events[0]["sequence"] == 0
    assert events[1]["sequence"] == 1


def test_event_stream_builder_includes_optional_fields() -> None:
    usage = ProviderUsage(total_tokens=100, latency_ms=50)
    limits = ExecutorLimits(
        max_prompt_tokens=1000,
        max_completion_tokens=500,
        max_total_tokens=1500,
        max_cost_usd=1.0,
        max_tool_calls=10,
        provider_timeout_ms=30000,
        max_attempts=3,
    )
    artifact = ExecutorArtifactRef(path="out.txt", scope="workspace")
    builder = EventStreamBuilder(
        run_id="r1",
        attempt_id="a1",
        ticket_id="T-001",
        executor_version="test",
        repo_head="abc123",
    )
    event = builder.append(
        "provider.responded",
        "succeeded",
        payload={"key": "value"},
        usage=usage,
        limits=limits,
        artifact_refs=(artifact,),
        error={"kind": "test", "message": "err"},
    )
    assert event["repo_head"] == "abc123"
    assert event["payload"] == {"key": "value"}
    assert "usage" in event
    assert "limits" in event
    assert len(event["artifact_refs"]) == 1
    assert event["error"]["kind"] == "test"


def test_event_stream_builder_omits_empty_usage() -> None:
    usage = ProviderUsage()
    builder = EventStreamBuilder(
        run_id="r1",
        attempt_id="a1",
        ticket_id="T-001",
        executor_version="test",
    )
    event = builder.append("test", "ok", usage=usage)
    assert "usage" not in event


def test_attempt_summary_builder_basic() -> None:
    builder = AttemptSummaryBuilder(
        run_id="r1",
        attempt_id="a1",
        ticket_id="T-001",
        started_at="2026-01-15T10:00:00Z",
    )
    summary = builder.build(
        final_result="succeeded",
        provider="openrouter",
        model="test-model",
        tool_call_count=3,
        retry_count=1,
    )
    assert summary["schema_version"] == 1
    assert summary["final_result"] == "succeeded"
    assert summary["provider"] == "openrouter"
    assert summary["model"] == "test-model"
    assert summary["tool_call_count"] == 3
    assert summary["retry_count"] == 1
    assert summary["started_at"] == "2026-01-15T10:00:00Z"
    assert "ended_at" in summary


def test_attempt_summary_builder_includes_duration_from_usage() -> None:
    usage = ProviderUsage(latency_ms=250, total_tokens=100)
    builder = AttemptSummaryBuilder(
        run_id="r1",
        attempt_id="a1",
        ticket_id="T-001",
        started_at="2026-01-15T10:00:00Z",
    )
    summary = builder.build(
        final_result="succeeded",
        provider="local",
        model="llama",
        tool_call_count=0,
        retry_count=0,
        usage=usage,
    )
    assert summary["duration_ms"] == 250
    assert "usage" in summary


def test_attempt_summary_builder_omits_none_provider() -> None:
    builder = AttemptSummaryBuilder(
        run_id="r1",
        attempt_id="a1",
        ticket_id="T-001",
    )
    summary = builder.build(
        final_result="blocked",
        provider=None,
        model=None,
        tool_call_count=0,
        retry_count=0,
    )
    assert "provider" not in summary
    assert "model" not in summary
