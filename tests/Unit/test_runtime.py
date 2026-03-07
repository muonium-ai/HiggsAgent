from __future__ import annotations

import json
from pathlib import Path

from higgs_agent.application import DispatchOutcome
from higgs_agent.providers.contract import ProviderExecutionResult
from higgs_agent.routing import NormalizedTicketSemantics, RouteDecision
from higgs_agent.tickets import TicketRecord
from higgs_agent.runtime import persist_dispatch_outcome
from higgs_agent.validation import ValidationDecision


def test_persist_dispatch_outcome_writes_events_attempt_summary_and_artifacts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outcome = DispatchOutcome(
        ticket=TicketRecord(
            path=repo_root / "tickets" / "T-123.md",
            frontmatter={"id": "T-123", "status": "ready", "priority": "p1"},
            body="Body",
        ),
        semantics=NormalizedTicketSemantics(
            ticket_id="T-123",
            work_type="docs",
            priority="p1",
            platform="agnostic",
            complexity="low",
            execution_target="hosted",
            tool_profile="none",
            labels=(),
            tags=(),
            warnings=(),
        ),
        route=RouteDecision(
            ticket_id="T-123",
            priority="p1",
            selected=True,
            provider="openrouter",
            model_id="openai/gpt-4.1",
            route_family="balanced",
            estimated_cost_usd=1.0,
            requires_tool_calls=False,
            blocked_reason=None,
            rationale=("selected_model:openai/gpt-4.1",),
        ),
        execution_result=ProviderExecutionResult(
            status="succeeded",
            output_text="Generated patch summary.",
            tool_calls=(),
            usage=None,
            events=(
                {
                    "schema_version": 1,
                    "event_id": "event-1",
                    "event_type": "execution.created",
                    "occurred_at": "2026-03-07T00:00:00Z",
                    "sequence": 0,
                    "run_id": "run-123",
                    "attempt_id": "attempt-1",
                    "ticket_id": "T-123",
                    "status": "started",
                    "executor_version": "phase-1",
                },
            ),
            attempt_summary={
                "schema_version": 1,
                "run_id": "run-123",
                "attempt_id": "attempt-1",
                "ticket_id": "T-123",
                "started_at": "2026-03-07T00:00:00Z",
                "ended_at": "2026-03-07T00:00:01Z",
                "final_result": "succeeded",
                "tool_call_count": 0,
                "retry_count": 0,
            },
            retry_count=0,
            metadata={},
        ),
        validation_decision=ValidationDecision(
            decision="handoff_required",
            reason="protected_path_touched",
            diagnostics=("protected_paths:pyproject.toml",),
            changed_paths=("pyproject.toml",),
            requires_human_review=True,
            handoff_message="Review this output.",
        ),
    )

    persisted = persist_dispatch_outcome(repo_root=repo_root, outcome=outcome)

    telemetry_paths = persisted.execution_result.metadata["telemetry_paths"]
    events_path = repo_root / telemetry_paths["events"]
    artifacts_dir = repo_root / telemetry_paths["artifacts_dir"]
    attempt_summaries_path = repo_root / telemetry_paths["attempt_summaries"]

    assert events_path.is_file()
    assert artifacts_dir.is_dir()
    assert (artifacts_dir / "output.txt").read_text() == "Generated patch summary."
    assert (artifacts_dir / "review-handoff.txt").read_text() == "Review this output."

    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert events[-1]["event_type"] == "artifact.recorded"
    summaries = [json.loads(line) for line in attempt_summaries_path.read_text().splitlines()]
    assert summaries[0]["run_id"] == "run-123"
    assert len(summaries[0]["artifact_refs"]) == 2