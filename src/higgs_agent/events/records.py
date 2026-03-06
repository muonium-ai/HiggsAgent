"""Helpers for schema-aligned execution events and attempt summaries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from higgs_agent.providers.contract import ExecutorArtifactRef, ExecutorLimits, ProviderUsage


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class EventStreamBuilder:
    """Append-only schema-aligned execution event builder."""

    run_id: str
    attempt_id: str
    ticket_id: str
    executor_version: str
    repo_head: str | None = None
    _sequence: int = 0
    _events: list[dict[str, object]] = field(default_factory=list)

    def append(
        self,
        event_type: str,
        status: str,
        *,
        payload: dict[str, object] | None = None,
        usage: ProviderUsage | None = None,
        limits: ExecutorLimits | None = None,
        artifact_refs: tuple[ExecutorArtifactRef, ...] = (),
        error: dict[str, object] | None = None,
    ) -> dict[str, object]:
        event: dict[str, object] = {
            "schema_version": 1,
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "occurred_at": utc_now_iso(),
            "sequence": self._sequence,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "ticket_id": self.ticket_id,
            "status": status,
            "executor_version": self.executor_version,
        }
        if self.repo_head is not None:
            event["repo_head"] = self.repo_head
        if payload is not None:
            event["payload"] = payload
        if usage is not None:
            usage_payload = usage.as_schema_payload()
            if usage_payload:
                event["usage"] = usage_payload
        if limits is not None:
            event["limits"] = limits.as_event_limits()
        if artifact_refs:
            event["artifact_refs"] = [artifact.as_schema_payload() for artifact in artifact_refs]
        if error is not None:
            event["error"] = error

        self._events.append(event)
        self._sequence += 1
        return event

    def build(self) -> tuple[dict[str, object], ...]:
        return tuple(self._events)


@dataclass(slots=True)
class AttemptSummaryBuilder:
    """Builder for schema-aligned execution attempt summaries."""

    run_id: str
    attempt_id: str
    ticket_id: str
    started_at: str = field(default_factory=utc_now_iso)

    def build(
        self,
        *,
        final_result: str,
        provider: str | None,
        model: str | None,
        tool_call_count: int,
        retry_count: int,
        usage: ProviderUsage | None = None,
        artifact_refs: tuple[ExecutorArtifactRef, ...] = (),
        error: dict[str, object] | None = None,
        ended_at: str | None = None,
    ) -> dict[str, object]:
        end_time = ended_at or utc_now_iso()
        summary: dict[str, object] = {
            "schema_version": 1,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "ticket_id": self.ticket_id,
            "started_at": self.started_at,
            "ended_at": end_time,
            "final_result": final_result,
            "tool_call_count": tool_call_count,
            "retry_count": retry_count,
        }
        if provider is not None:
            summary["provider"] = provider
        if model is not None:
            summary["model"] = model
        if usage is not None:
            usage_payload = usage.as_schema_payload()
            if usage_payload:
                summary["usage"] = usage_payload
                latency = usage_payload.get("latency_ms")
                if isinstance(latency, int):
                    summary["duration_ms"] = latency
        if artifact_refs:
            summary["artifact_refs"] = [artifact.as_schema_payload() for artifact in artifact_refs]
        if error is not None:
            summary["error"] = error
        return summary