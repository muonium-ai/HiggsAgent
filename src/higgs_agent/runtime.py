"""First-party runtime helpers for executing a ticketed project workflow."""

from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from higgs_agent.application import DispatchOutcome, dispatch_next_ready_ticket
from higgs_agent.events import EventStreamBuilder
from higgs_agent.events.records import utc_now_iso
from higgs_agent.providers.contract import ExecutorArtifactRef, ExecutorInput, ProviderExecutionResult
from higgs_agent.providers.hosted import OpenRouterExecutor, OpenRouterHTTPTransport, load_executor_limits
from higgs_agent.routing import choose_route, classify_ticket, load_route_guardrails
from higgs_agent.tickets import TicketRecord, scan_ticket_directory, select_next_ready_ticket
from higgs_agent.validation import (
    ProposedFileChange,
    ValidationDecision,
    ValidationInput,
    evaluate_write_request,
    load_write_policy,
)


class RuntimeConfigError(ValueError):
    """Raised when runtime inputs are invalid or incomplete."""


@dataclass(frozen=True, slots=True)
class AutonomousFileWrite:
    """Normalized full-file write requested by an autonomous session."""

    path: str
    content: str


@dataclass(frozen=True, slots=True)
class AutonomousFilePatch:
    """Normalized exact-match patch requested by an autonomous session."""

    path: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class AutonomousPlan:
    """Structured filesystem mutation plan returned by the coding model."""

    summary: str
    directories: tuple[str, ...]
    writes: tuple[AutonomousFileWrite, ...]
    patches: tuple[AutonomousFilePatch, ...]


@dataclass(frozen=True, slots=True)
class ValidationCommandResult:
    """Captured output from one configured validation command."""

    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True, slots=True)
class ProjectTicketAttempt:
    """One autonomous single-ticket attempt within a project run."""

    ticket_id: str
    execution_status: str
    validation_decision: str
    validation_reason: str | None
    telemetry_paths: dict[str, str]


@dataclass(frozen=True, slots=True)
class ProjectRunResult:
    """Project-level autonomous orchestration result."""

    project_run_id: str
    status: str
    terminal_condition: str
    resumed: bool
    retry_count: int
    commit_policy: str
    attempted_tickets: tuple[ProjectTicketAttempt, ...]
    completed_tickets: tuple[str, ...]
    checkpoint_path: Path
    summary_path: Path
    review_bundle_path: Path


def run_turnkey_project(
    *,
    repo_root: Path,
    requirements_path: Path,
    tickets_dir: Path,
    guardrails_path: Path,
    write_policy_path: Path,
    validation_commands: tuple[str, ...],
    openrouter_api_key: str,
    owner: str = "coordinator",
    muontickets_cli_path: Path | None = None,
    project_run_id: str | None = None,
    resume: bool = False,
    max_tickets: int | None = None,
    max_consecutive_failures: int = 1,
    create_local_commit: bool = False,
) -> ProjectRunResult:
    """Execute autonomous ticket runs until the repository reaches a terminal condition."""

    if not validation_commands:
        raise RuntimeConfigError("at least one validation command is required")
    if max_tickets is not None and max_tickets <= 0:
        raise RuntimeConfigError("max_tickets must be positive when provided")
    if max_consecutive_failures <= 0:
        raise RuntimeConfigError("max_consecutive_failures must be positive")
    if create_local_commit:
        raise RuntimeConfigError("turnkey-project local commit creation is not yet supported")

    repo_root = repo_root.resolve()
    run_id = project_run_id or f"project-run-{uuid4().hex[:12]}"
    run_dir = repo_root / ".higgs" / "local" / "project-runs" / run_id
    checkpoint_path = run_dir / "checkpoint.json"
    summary_path = run_dir / "summary.json"
    review_bundle_path = run_dir / "review-bundle.json"

    if resume:
        state = _load_project_run_state(checkpoint_path=checkpoint_path, expected_project_run_id=run_id)
        state["resumed"] = True
    else:
        if checkpoint_path.exists():
            raise RuntimeConfigError(
                f"project checkpoint already exists for {run_id}; pass --resume to continue it"
            )
        state = {
            "schema_version": 1,
            "project_run_id": run_id,
            "started_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "status": "running",
            "terminal_condition": None,
            "resumed": False,
            "retry_count": 0,
            "consecutive_failures": 0,
            "commit_policy": "disabled",
            "max_tickets": max_tickets,
            "max_consecutive_failures": max_consecutive_failures,
            "attempted_tickets": [],
            "completed_tickets": [],
        }
    _save_project_run_state(checkpoint_path, state)

    while True:
        if max_tickets is not None and len(state["attempted_tickets"]) >= max_tickets:
            return _finalize_project_run(
                state,
                checkpoint_path=checkpoint_path,
                summary_path=summary_path,
                review_bundle_path=review_bundle_path,
                tickets_dir=tickets_dir,
                status="stopped",
                terminal_condition="max_ticket_limit_reached",
            )
        try:
            outcome = run_autonomous_ticket(
                repo_root=repo_root,
                requirements_path=requirements_path,
                tickets_dir=tickets_dir,
                guardrails_path=guardrails_path,
                write_policy_path=write_policy_path,
                validation_commands=validation_commands,
                openrouter_api_key=openrouter_api_key,
                owner=owner,
                muontickets_cli_path=muontickets_cli_path,
            )
        except RuntimeConfigError as exc:
            if "no ready tickets found" not in str(exc):
                attempted_tickets = list(state["attempted_tickets"])
                attempted_tickets.append(
                    {
                        "ticket_id": "(runtime)",
                        "execution_status": "failed",
                        "validation_decision": "rejected",
                        "validation_reason": str(exc),
                        "telemetry_paths": {},
                    }
                )
                state["attempted_tickets"] = attempted_tickets
                state["retry_count"] = int(state["retry_count"]) + 1
                state["consecutive_failures"] = int(state["consecutive_failures"]) + 1
                state["updated_at"] = utc_now_iso()
                _save_project_run_state(checkpoint_path, state)
                if int(state["consecutive_failures"]) >= max_consecutive_failures:
                    return _finalize_project_run(
                        state,
                        checkpoint_path=checkpoint_path,
                        summary_path=summary_path,
                        review_bundle_path=review_bundle_path,
                        tickets_dir=tickets_dir,
                        status="blocked",
                        terminal_condition="repeated_failures_exceeded",
                    )
                continue
            terminal_condition = _determine_no_ready_terminal_condition(tickets_dir)
            status = "blocked" if terminal_condition == "blocked_dependency_graph" else "succeeded"
            return _finalize_project_run(
                state,
                checkpoint_path=checkpoint_path,
                summary_path=summary_path,
                review_bundle_path=review_bundle_path,
                tickets_dir=tickets_dir,
                status=status,
                terminal_condition=terminal_condition,
            )

        attempt_record = {
            "ticket_id": outcome.ticket.id,
            "execution_status": outcome.execution_result.status,
            "validation_decision": outcome.validation_decision.decision,
            "validation_reason": outcome.validation_decision.reason,
            "telemetry_paths": dict(outcome.execution_result.metadata.get("telemetry_paths", {})),
        }
        attempted_tickets = list(state["attempted_tickets"])
        attempted_tickets.append(attempt_record)
        state["attempted_tickets"] = attempted_tickets

        if outcome.validation_decision.decision == "accepted":
            completed_tickets = list(state["completed_tickets"])
            completed_tickets.append(outcome.ticket.id)
            state["completed_tickets"] = completed_tickets
            state["consecutive_failures"] = 0
            state["updated_at"] = utc_now_iso()
            _save_project_run_state(checkpoint_path, state)
            continue

        terminal_condition = _terminal_condition_for_outcome(outcome.validation_decision)
        return _finalize_project_run(
            state,
            checkpoint_path=checkpoint_path,
            summary_path=summary_path,
            review_bundle_path=review_bundle_path,
            tickets_dir=tickets_dir,
            status="blocked",
            terminal_condition=terminal_condition,
        )


def _finalize_project_run(
    state: dict[str, Any],
    *,
    checkpoint_path: Path,
    summary_path: Path,
    review_bundle_path: Path,
    tickets_dir: Path,
    status: str,
    terminal_condition: str,
) -> ProjectRunResult:
    state["status"] = status
    state["terminal_condition"] = terminal_condition
    state["updated_at"] = utc_now_iso()
    _save_project_run_state(checkpoint_path, state)
    _save_project_run_summary(summary_path, state)
    _write_project_review_bundle(review_bundle_path=review_bundle_path, tickets_dir=tickets_dir, state=state)
    return _build_project_run_result(
        state,
        checkpoint_path=checkpoint_path,
        summary_path=summary_path,
        review_bundle_path=review_bundle_path,
    )


def _determine_no_ready_terminal_condition(tickets_dir: Path) -> str:
    scan_result = scan_ticket_directory(tickets_dir)
    if any(
        decision.reason.startswith("blocked_by_dependency") or decision.reason.startswith("missing_dependency")
        for decision in scan_result.decisions
    ):
        return "blocked_dependency_graph"
    return "no_ready_ticket"


def _terminal_condition_for_outcome(validation_decision: ValidationDecision) -> str:
    if validation_decision.decision == "handoff_required":
        return "review_handoff_required"
    if validation_decision.reason == "validation_failed":
        return "validation_failure"
    return "ticket_rejected"


def _load_project_run_state(*, checkpoint_path: Path, expected_project_run_id: str) -> dict[str, Any]:
    if not checkpoint_path.exists():
        raise RuntimeConfigError(f"project checkpoint not found for {expected_project_run_id}: {checkpoint_path}")
    payload = json.loads(checkpoint_path.read_text())
    if payload.get("project_run_id") != expected_project_run_id:
        raise RuntimeConfigError(
            f"project checkpoint id mismatch: expected {expected_project_run_id}, found {payload.get('project_run_id')}"
        )
    payload.setdefault("retry_count", 0)
    payload.setdefault("consecutive_failures", 0)
    payload.setdefault("commit_policy", "disabled")
    payload.setdefault("max_tickets", None)
    payload.setdefault("max_consecutive_failures", 1)
    return payload


def _save_project_run_state(checkpoint_path: Path, state: dict[str, Any]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def _save_project_run_summary(summary_path: Path, state: dict[str, Any]) -> None:
    summary = {
        "schema_version": state["schema_version"],
        "project_run_id": state["project_run_id"],
        "status": state["status"],
        "terminal_condition": state["terminal_condition"],
        "resumed": state["resumed"],
        "retry_count": state["retry_count"],
        "commit_policy": state["commit_policy"],
        "attempted_tickets": state["attempted_tickets"],
        "completed_tickets": state["completed_tickets"],
        "updated_at": state["updated_at"],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


def _write_project_review_bundle(
    *,
    review_bundle_path: Path,
    tickets_dir: Path,
    state: dict[str, Any],
) -> None:
    scan_result = scan_ticket_directory(tickets_dir)
    completed_ids = set(state["completed_tickets"])
    attempted_ids = {
        record["ticket_id"]
        for record in state["attempted_tickets"]
        if record["ticket_id"] != "(runtime)"
    }
    blocked_by_attempt = [
        {
            "ticket_id": record["ticket_id"],
            "reason": record.get("validation_reason") or record["validation_decision"],
        }
        for record in state["attempted_tickets"]
        if record["ticket_id"] != "(runtime)" and record["validation_decision"] != "accepted"
    ]
    untouched_tickets = [
        {
            "ticket_id": record.id,
            "status": record.status,
            "reason": scan_result.decision_for(record.id).reason if scan_result.decision_for(record.id) else "unknown",
        }
        for record in scan_result.tickets
        if record.id not in completed_ids and record.id not in attempted_ids
    ]
    blocked_graph_tickets = [
        {
            "ticket_id": decision.ticket_id,
            "reason": decision.reason,
        }
        for decision in scan_result.decisions
        if not decision.eligible
        and decision.ticket_id not in completed_ids
        and decision.reason.startswith(("blocked_by_dependency", "missing_dependency"))
    ]
    bundle = {
        "schema_version": state["schema_version"],
        "project_run_id": state["project_run_id"],
        "status": state["status"],
        "terminal_condition": state["terminal_condition"],
        "commit_policy": state["commit_policy"],
        "retry_count": state["retry_count"],
        "completed_tickets": list(state["completed_tickets"]),
        "blocked_tickets": blocked_by_attempt + blocked_graph_tickets,
        "untouched_tickets": untouched_tickets,
        "attempted_tickets": state["attempted_tickets"],
    }
    review_bundle_path.parent.mkdir(parents=True, exist_ok=True)
    review_bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")


def _build_project_run_result(
    state: dict[str, Any],
    *,
    checkpoint_path: Path,
    summary_path: Path,
    review_bundle_path: Path,
) -> ProjectRunResult:
    attempts = tuple(
        ProjectTicketAttempt(
            ticket_id=record["ticket_id"],
            execution_status=record["execution_status"],
            validation_decision=record["validation_decision"],
            validation_reason=record.get("validation_reason"),
            telemetry_paths=dict(record.get("telemetry_paths", {})),
        )
        for record in state["attempted_tickets"]
    )
    return ProjectRunResult(
        project_run_id=state["project_run_id"],
        status=state["status"],
        terminal_condition=state["terminal_condition"] or "running",
        resumed=bool(state.get("resumed", False)),
        retry_count=int(state.get("retry_count", 0)),
        commit_policy=str(state.get("commit_policy", "disabled")),
        attempted_tickets=attempts,
        completed_tickets=tuple(state["completed_tickets"]),
        checkpoint_path=checkpoint_path,
        summary_path=summary_path,
        review_bundle_path=review_bundle_path,
    )


def parse_changed_file_spec(spec: str) -> ProposedFileChange:
    """Parse a CLI changed-file spec into a normalized proposed file change."""

    parts = spec.split(":")
    if len(parts) not in {3, 4}:
        raise RuntimeConfigError(
            "--changed-file must be PATH:ADDITIONS:DELETIONS[:binary]"
        )

    path, additions_text, deletions_text, *binary_part = parts
    if not path:
        raise RuntimeConfigError("--changed-file path must not be empty")
    try:
        additions = int(additions_text)
        deletions = int(deletions_text)
    except ValueError as exc:
        raise RuntimeConfigError(
            f"--changed-file additions and deletions must be integers: {spec}"
        ) from exc
    if additions < 0 or deletions < 0:
        raise RuntimeConfigError(
            f"--changed-file additions and deletions must be non-negative: {spec}"
        )

    is_binary = False
    if binary_part:
        binary_value = binary_part[0].strip().lower()
        if binary_value not in {"binary", "text"}:
            raise RuntimeConfigError(
                f"--changed-file binary marker must be 'binary' or 'text': {spec}"
            )
        is_binary = binary_value == "binary"

    return ProposedFileChange(
        path=path,
        additions=additions,
        deletions=deletions,
        is_binary=is_binary,
    )


def run_ticketed_project(
    *,
    repo_root: Path,
    requirements_path: Path,
    tickets_dir: Path,
    guardrails_path: Path,
    write_policy_path: Path,
    changed_files: tuple[ProposedFileChange, ...],
    validation_summary: str,
    openrouter_api_key: str,
) -> DispatchOutcome:
    """Execute the next ready ticket using explicit runtime inputs."""

    requirements_text = requirements_path.read_text()
    transport = OpenRouterHTTPTransport(api_key=openrouter_api_key)
    outcome = dispatch_next_ready_ticket(
        tickets_dir,
        transport=transport,
        guardrails_path=guardrails_path,
        write_policy_path=write_policy_path,
        planned_changes=changed_files,
        validation_summary=validation_summary,
        requirements_text=requirements_text,
        run_id=f"run-{uuid4().hex[:12]}",
        attempt_id="attempt-1",
        repo_head=_read_repo_head(repo_root),
    )
    if outcome is None:
        raise RuntimeConfigError(f"no ready tickets found in {tickets_dir}")
    return persist_dispatch_outcome(repo_root=repo_root, outcome=outcome)


def run_autonomous_ticket(
    *,
    repo_root: Path,
    requirements_path: Path,
    tickets_dir: Path,
    guardrails_path: Path,
    write_policy_path: Path,
    validation_commands: tuple[str, ...],
    openrouter_api_key: str,
    owner: str = "coordinator",
    muontickets_cli_path: Path | None = None,
    transport=None,
) -> DispatchOutcome:
    """Execute one autonomous single-ticket coding session against the next ready ticket."""

    if not validation_commands:
        raise RuntimeConfigError("at least one validation command is required")

    scan_result = scan_ticket_directory(tickets_dir)
    ticket = select_next_ready_ticket(scan_result)
    if ticket is None:
        raise RuntimeConfigError(f"no ready tickets found in {tickets_dir}")

    repo_root = repo_root.resolve()
    requirements_text = requirements_path.read_text()
    workspace_snapshot = _collect_workspace_snapshot(repo_root=repo_root, tickets_dir=tickets_dir)
    mt_cli_path = muontickets_cli_path or _default_muontickets_cli(repo_root)
    _require_file_exists(mt_cli_path, flag_name="--muontickets-cli")

    _run_muontickets_command(mt_cli_path, ["claim", ticket.id, "--owner", owner], cwd=repo_root)

    semantics = classify_ticket(ticket)
    route_guardrails = load_route_guardrails(guardrails_path)
    route = choose_route(semantics, route_guardrails, local_execution_enabled=False)

    executor = OpenRouterExecutor(
        limits=load_executor_limits(guardrails_path),
        transport=transport or OpenRouterHTTPTransport(api_key=openrouter_api_key),
    )
    execution_input = ExecutorInput(
        ticket_id=ticket.id,
        run_id=f"run-{uuid4().hex[:12]}",
        attempt_id="attempt-1",
        route=route,
        prompt=_build_autonomous_prompt(
            ticket=ticket,
            requirements_text=requirements_text,
            workspace_snapshot=workspace_snapshot,
        ),
        system_prompt=(
            "You are HiggsAgent autonomous coding runtime. "
            "Return only a JSON object matching the requested schema."
        ),
        repo_head=_read_repo_head(repo_root),
        allow_tool_calls=False,
    )
    execution_result = executor.execute(execution_input)
    execution_result = _append_event(
        execution_result,
        event_type="prompt.rendered",
        status="succeeded",
        payload={"mode": "autonomous_ticket", "workspace_files": len(workspace_snapshot)},
    )
    execution_result = _append_event(
        execution_result,
        event_type="workspace.read",
        status="succeeded",
        payload={"paths": [item["path"] for item in workspace_snapshot]},
    )

    changed_files: tuple[ProposedFileChange, ...] = ()
    validation_results: tuple[ValidationCommandResult, ...] = ()
    if execution_result.status == "succeeded":
        try:
            plan = _parse_autonomous_plan(execution_result.output_text)
            changed_files, execution_result = _apply_autonomous_plan(
                repo_root=repo_root,
                execution_result=execution_result,
                plan=plan,
            )
        except RuntimeConfigError as exc:
            execution_result = _mark_execution_failed(
                execution_result,
                error_kind="materialization_failure",
                message=str(exc),
            )

    if execution_result.status == "succeeded":
        validation_results, execution_result = _run_validation_commands(
            repo_root=repo_root,
            commands=validation_commands,
            execution_result=execution_result,
        )

    validation_summary = _render_validation_summary(validation_results)
    validation_decision = _evaluate_autonomous_write_request(
        ticket=ticket,
        execution_result=execution_result,
        changed_files=changed_files,
        validation_summary=validation_summary,
        validation_passed=all(result.passed for result in validation_results) if validation_results else False,
        write_policy_path=write_policy_path,
    )

    execution_result = _with_runtime_validation_events(
        execution_result,
        validation_decision=validation_decision,
        validation_summary=validation_summary,
    )

    if execution_result.status == "succeeded" and validation_decision.decision != "rejected":
        _run_muontickets_command(
            mt_cli_path,
            [
                "comment",
                ticket.id,
                (
                    f"Autonomous run completed. Validation decision: {validation_decision.decision}. "
                    f"Changed paths: {', '.join(validation_decision.changed_paths) or 'none'}."
                ),
            ],
            cwd=repo_root,
        )
        execution_result = _append_event(
            execution_result,
            event_type="ticket.workflow.updated",
            status="succeeded",
            payload={"action": "comment", "ticket_id": ticket.id},
        )
        _run_muontickets_command(mt_cli_path, ["set-status", ticket.id, "needs_review"], cwd=repo_root)
        execution_result = _append_event(
            execution_result,
            event_type="ticket.workflow.updated",
            status="succeeded",
            payload={"action": "set-status", "from": "claimed", "to": "needs_review", "ticket_id": ticket.id},
        )
    else:
        _run_muontickets_command(
            mt_cli_path,
            [
                "comment",
                ticket.id,
                (
                    f"Autonomous run blocked. Validation decision: {validation_decision.decision}. "
                    f"Reason: {validation_decision.reason}."
                ),
            ],
            cwd=repo_root,
        )
        execution_result = _append_event(
            execution_result,
            event_type="ticket.workflow.updated",
            status="succeeded",
            payload={"action": "comment", "ticket_id": ticket.id, "reason": validation_decision.reason},
        )

    outcome = DispatchOutcome(
        ticket=ticket,
        semantics=semantics,
        route=route,
        execution_result=execution_result,
        validation_decision=validation_decision,
    )
    return persist_dispatch_outcome(repo_root=repo_root, outcome=outcome)


def persist_dispatch_outcome(*, repo_root: Path, outcome: DispatchOutcome) -> DispatchOutcome:
    """Persist concrete local telemetry for a completed dispatch attempt."""

    run_dir = (
        repo_root
        / ".higgs"
        / "local"
        / "runs"
        / outcome.execution_result.attempt_summary["run_id"]
        / outcome.execution_result.attempt_summary["attempt_id"]
    )
    artifacts_dir = run_dir / "artifacts"
    analytics_dir = repo_root / ".higgs" / "local" / "analytics"
    events_path = run_dir / "events.ndjson"
    attempt_summaries_path = analytics_dir / "attempt-summaries.ndjson"

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    analytics_dir.mkdir(parents=True, exist_ok=True)

    artifact_refs: list[ExecutorArtifactRef] = []
    if outcome.execution_result.output_text:
        artifact_refs.append(
            _write_text_artifact(
                artifacts_dir / "output.txt",
                outcome.execution_result.output_text,
                repo_root=repo_root,
            )
        )
    if outcome.validation_decision.handoff_message:
        artifact_refs.append(
            _write_text_artifact(
                artifacts_dir / "review-handoff.txt",
                outcome.validation_decision.handoff_message,
                repo_root=repo_root,
            )
        )
    materialization_plan = outcome.execution_result.metadata.get("materialization_plan")
    if materialization_plan is not None:
        artifact_refs.append(
            _write_text_artifact(
                artifacts_dir / "materialization-plan.json",
                json.dumps(materialization_plan, indent=2, sort_keys=True) + "\n",
                repo_root=repo_root,
            )
        )

    updated_events = list(outcome.execution_result.events)
    if artifact_refs:
        updated_events.append(
            {
                "schema_version": 1,
                "event_id": str(uuid4()),
                "event_type": "artifact.recorded",
                "occurred_at": utc_now_iso(),
                "sequence": len(updated_events),
                "run_id": outcome.execution_result.attempt_summary["run_id"],
                "attempt_id": outcome.execution_result.attempt_summary["attempt_id"],
                "ticket_id": outcome.execution_result.attempt_summary["ticket_id"],
                "status": "succeeded",
                "executor_version": "phase-1",
                "artifact_refs": [artifact.as_schema_payload() for artifact in artifact_refs],
            }
        )

    _write_ndjson(events_path, updated_events)

    updated_attempt_summary = dict(outcome.execution_result.attempt_summary)
    if artifact_refs:
        updated_attempt_summary["artifact_refs"] = [artifact.as_schema_payload() for artifact in artifact_refs]
    _append_ndjson_line(attempt_summaries_path, updated_attempt_summary)

    updated_execution_result = replace(
        outcome.execution_result,
        events=tuple(updated_events),
        attempt_summary=updated_attempt_summary,
        metadata={
            **outcome.execution_result.metadata,
            "telemetry_paths": {
                "events": str(events_path.relative_to(repo_root)),
                "artifacts_dir": str(artifacts_dir.relative_to(repo_root)),
                "attempt_summaries": str(attempt_summaries_path.relative_to(repo_root)),
            },
        },
    )
    return replace(outcome, execution_result=updated_execution_result)


def _read_repo_head(repo_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    head = completed.stdout.strip()
    return head or None


def _write_text_artifact(path: Path, content: str, *, repo_root: Path) -> ExecutorArtifactRef:
    path.write_text(content)
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ExecutorArtifactRef(
        path=str(path.relative_to(repo_root)),
        scope="local",
        sha256=sha256,
        size_bytes=path.stat().st_size,
    )


def _write_ndjson(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))


def _append_ndjson_line(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _build_autonomous_prompt(
    *,
    ticket: TicketRecord,
    requirements_text: str,
    workspace_snapshot: tuple[dict[str, str], ...],
) -> str:
    workspace_sections = []
    for item in workspace_snapshot:
        workspace_sections.append(f"Path: {item['path']}\n```\n{item['content']}\n```")
    workspace_text = "\n\n".join(workspace_sections) if workspace_sections else "No existing workspace files captured."
    title = ticket.frontmatter.get("title", ticket.id)
    body = ticket.body.strip() or "No additional ticket body."
    return "\n\n".join(
        [
            f"Ticket: {ticket.id} - {title}",
            f"Ticket details:\n{body}",
            f"Project requirements:\n{requirements_text.strip()}",
            (
                "Current workspace snapshot:\n"
                f"{workspace_text}"
            ),
            (
                "Return only valid JSON with this shape: "
                '{"summary": "short summary", "directories": ["relative/path"], '
                '"writes": [{"path": "relative/file.py", "content": "full file contents"}], '
                '"patches": [{"path": "relative/file.py", "before": "exact existing text", '
                '"after": "replacement text"}]}'
            ),
            (
                "Use repository-relative paths only. Patch entries must target existing files and replace a single "
                "exact matched snippet. Do not include markdown fences outside JSON."
            ),
        ]
    )


def _collect_workspace_snapshot(
    *,
    repo_root: Path,
    tickets_dir: Path,
    max_files: int = 20,
    max_chars_per_file: int = 6000,
) -> tuple[dict[str, str], ...]:
    snapshot: list[dict[str, str]] = []
    ignored_roots = {repo_root / ".git", repo_root / ".higgs", tickets_dir.resolve()}
    for path in sorted(repo_root.rglob("*")):
        if len(snapshot) >= max_files:
            break
        if not path.is_file():
            continue
        if any(parent == ignored_root for ignored_root in ignored_roots for parent in [path, *path.parents]):
            continue
        try:
            content = path.read_text()
        except UnicodeDecodeError:
            continue
        snapshot.append(
            {
                "path": str(path.relative_to(repo_root)).replace("\\", "/"),
                "content": content[:max_chars_per_file],
            }
        )
    return tuple(snapshot)


def _parse_autonomous_plan(output_text: str) -> AutonomousPlan:
    payload = _extract_json_payload(output_text)
    if not isinstance(payload, dict):
        raise RuntimeConfigError("autonomous response must be a JSON object")
    summary = payload.get("summary", "")
    if not isinstance(summary, str):
        raise RuntimeConfigError("autonomous response 'summary' must be a string")
    scaffold_payload = payload.get("scaffold")
    if scaffold_payload is not None and not isinstance(scaffold_payload, dict):
        raise RuntimeConfigError("autonomous response 'scaffold' must be an object when present")

    raw_directories = payload.get("directories", [])
    if raw_directories is None:
        raw_directories = []
    if not isinstance(raw_directories, list) or not all(isinstance(item, str) for item in raw_directories):
        raise RuntimeConfigError("autonomous response 'directories' must be a list of strings")
    raw_writes = payload.get("writes", payload.get("files", []))
    if raw_writes is None:
        raw_writes = []
    if not isinstance(raw_writes, list):
        raise RuntimeConfigError("autonomous response 'writes' must be a list")
    raw_patches = payload.get("patches", payload.get("diffs", []))
    if raw_patches is None:
        raw_patches = []
    if not isinstance(raw_patches, list):
        raise RuntimeConfigError("autonomous response 'patches' must be a list")

    writes: list[AutonomousFileWrite] = []
    for raw_write in raw_writes:
        if not isinstance(raw_write, dict):
            raise RuntimeConfigError("autonomous response write entries must be objects")
        path = raw_write.get("path")
        content = raw_write.get("content", raw_write.get("text"))
        if not isinstance(path, str) or not isinstance(content, str):
            raise RuntimeConfigError("autonomous response writes require string 'path' and 'content'")
        writes.append(AutonomousFileWrite(path=path, content=content))

    patches = _parse_autonomous_patch_entries(raw_patches, context_label="response")

    directories = list(raw_directories)
    if scaffold_payload is not None:
        scaffold_directories, scaffold_writes = _parse_scaffold_payload(scaffold_payload)
        directories.extend(scaffold_directories)
        writes.extend(scaffold_writes)

    _reject_duplicate_materialization_paths(directories, writes, patches)

    if not directories and not writes and not patches:
        raise RuntimeConfigError(
            "autonomous response did not describe any scaffold directories, file writes, or patch operations"
        )

    return AutonomousPlan(
        summary=summary,
        directories=tuple(directories),
        writes=tuple(writes),
        patches=tuple(patches),
    )


def _parse_autonomous_patch_entries(
    raw_patches: list[object], *, context_label: str
) -> list[AutonomousFilePatch]:
    patches: list[AutonomousFilePatch] = []
    for raw_patch in raw_patches:
        if not isinstance(raw_patch, dict):
            raise RuntimeConfigError(f"autonomous {context_label} patch entries must be objects")
        path = raw_patch.get("path")
        before = raw_patch.get("before", raw_patch.get("find", raw_patch.get("old_text")))
        after = raw_patch.get("after", raw_patch.get("replace", raw_patch.get("new_text")))
        if not isinstance(path, str) or not path:
            raise RuntimeConfigError(f"autonomous {context_label} patch entries require a non-empty string 'path'")
        if not isinstance(before, str) or not before:
            raise RuntimeConfigError(
                f"autonomous {context_label} patch entries require a non-empty string 'before'"
            )
        if not isinstance(after, str):
            raise RuntimeConfigError(f"autonomous {context_label} patch entries require string 'after'")
        patches.append(AutonomousFilePatch(path=path, before=before, after=after))
    return patches


def _parse_scaffold_payload(payload: dict[str, object]) -> tuple[list[str], list[AutonomousFileWrite]]:
    raw_directories = payload.get("directories", [])
    if raw_directories is None:
        raw_directories = []
    if not isinstance(raw_directories, list) or not all(isinstance(item, str) for item in raw_directories):
        raise RuntimeConfigError("autonomous scaffold 'directories' must be a list of strings")

    raw_files = payload.get("files", payload.get("writes", []))
    if raw_files is None:
        raw_files = []
    if not isinstance(raw_files, list):
        raise RuntimeConfigError("autonomous scaffold 'files' must be a list when present")

    writes: list[AutonomousFileWrite] = []
    for raw_file in raw_files:
        if not isinstance(raw_file, dict):
            raise RuntimeConfigError("autonomous scaffold file entries must be objects")
        path = raw_file.get("path")
        content = raw_file.get("content", raw_file.get("text"))
        if not isinstance(path, str) or not isinstance(content, str):
            raise RuntimeConfigError("autonomous scaffold file entries require string 'path' and 'content'")
        writes.append(AutonomousFileWrite(path=path, content=content))

    raw_tree = payload.get("tree", payload.get("entries", []))
    if raw_tree is None:
        raw_tree = []
    if not isinstance(raw_tree, list):
        raise RuntimeConfigError("autonomous scaffold 'tree' must be a list when present")

    directories = list(raw_directories)
    for entry in raw_tree:
        entry_directories, entry_writes = _parse_scaffold_tree_entry(entry, parent_prefix=Path("."))
        directories.extend(entry_directories)
        writes.extend(entry_writes)
    return directories, writes


def _parse_scaffold_tree_entry(entry: object, *, parent_prefix: Path) -> tuple[list[str], list[AutonomousFileWrite]]:
    if not isinstance(entry, dict):
        raise RuntimeConfigError("autonomous scaffold tree entries must be objects")
    entry_type = entry.get("type")
    path_text = entry.get("path")
    if not isinstance(entry_type, str) or entry_type not in {"directory", "file"}:
        raise RuntimeConfigError("autonomous scaffold tree entries require type 'directory' or 'file'")
    if not isinstance(path_text, str) or not path_text:
        raise RuntimeConfigError("autonomous scaffold tree entries require a non-empty string 'path'")

    relative_path = _normalize_relative_path(str(parent_prefix / path_text))
    children = entry.get("children", [])
    if children is None:
        children = []

    if entry_type == "directory":
        if "content" in entry or "text" in entry:
            raise RuntimeConfigError("directory scaffold entries must not declare file content")
        if not isinstance(children, list):
            raise RuntimeConfigError("directory scaffold children must be a list")
        directories = [str(relative_path).replace("\\", "/")]
        writes: list[AutonomousFileWrite] = []
        for child in children:
            child_directories, child_writes = _parse_scaffold_tree_entry(child, parent_prefix=relative_path)
            directories.extend(child_directories)
            writes.extend(child_writes)
        return directories, writes

    if children:
        raise RuntimeConfigError("file scaffold entries must not declare children")
    content = entry.get("content", entry.get("text"))
    if not isinstance(content, str):
        raise RuntimeConfigError("file scaffold entries require string 'content' or 'text'")
    return [], [AutonomousFileWrite(path=str(relative_path).replace("\\", "/"), content=content)]


def _reject_duplicate_materialization_paths(
    directories: list[str],
    writes: list[AutonomousFileWrite],
    patches: list[AutonomousFilePatch],
) -> None:
    duplicate_directories = _duplicate_items([str(_normalize_relative_path(directory)).replace("\\", "/") for directory in directories])
    if duplicate_directories:
        raise RuntimeConfigError(
            f"autonomous scaffold declared duplicate directories: {', '.join(sorted(duplicate_directories))}"
        )

    write_paths = [str(_normalize_relative_path(write.path)).replace("\\", "/") for write in writes]
    duplicate_writes = _duplicate_items(write_paths)
    if duplicate_writes:
        raise RuntimeConfigError(
            f"autonomous scaffold declared duplicate file writes: {', '.join(sorted(duplicate_writes))}"
        )

    patch_paths = [str(_normalize_relative_path(patch.path)).replace("\\", "/") for patch in patches]
    duplicate_patches = _duplicate_items(patch_paths)
    if duplicate_patches:
        raise RuntimeConfigError(
            f"autonomous scaffold declared duplicate file patches: {', '.join(sorted(duplicate_patches))}"
        )

    overlapping_paths = sorted(set(write_paths).intersection(patch_paths))
    if overlapping_paths:
        raise RuntimeConfigError(
            f"autonomous scaffold declared overlapping write and patch targets: {', '.join(overlapping_paths)}"
        )


def _duplicate_items(items: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
            continue
        seen.add(item)
    return duplicates


def _extract_json_payload(output_text: str) -> object:
    text = output_text.strip()
    if not text:
        raise RuntimeConfigError("autonomous response was empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced_start = text.find("```")
    if fenced_start != -1:
        fence_header_end = text.find("\n", fenced_start)
        fenced_end = text.rfind("```")
        if fence_header_end != -1 and fenced_end > fence_header_end:
            candidate = text[fence_header_end + 1:fenced_end].strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeConfigError(f"autonomous response did not contain valid JSON: {exc}") from exc
    raise RuntimeConfigError("autonomous response did not contain a JSON object")


def _apply_autonomous_plan(
    *,
    repo_root: Path,
    execution_result: ProviderExecutionResult,
    plan: AutonomousPlan,
) -> tuple[tuple[ProposedFileChange, ...], ProviderExecutionResult]:
    updated_result = replace(
        execution_result,
        metadata={
            **execution_result.metadata,
            "materialization_plan": {
                "summary": plan.summary,
                "directories": list(plan.directories),
                "writes": [write.path for write in plan.writes],
                "patches": [
                    {"path": patch.path, "before": patch.before, "after": patch.after}
                    for patch in plan.patches
                ],
            },
        },
    )
    for directory in plan.directories:
        relative_dir = _normalize_relative_path(directory)
        (repo_root / relative_dir).mkdir(parents=True, exist_ok=True)
        updated_result = _append_event(
            updated_result,
            event_type="directory.created",
            status="succeeded",
            payload={"path": str(relative_dir).replace("\\", "/")},
        )

    changed_files: list[ProposedFileChange] = []
    for write in plan.writes:
        relative_path = _normalize_relative_path(write.path)
        absolute_path = repo_root / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        before_content = absolute_path.read_text() if absolute_path.exists() else None
        absolute_path.write_text(write.content)
        if before_content == write.content:
            continue
        additions, deletions = _line_diff_stats(before_content or "", write.content)
        changed_files.append(
            ProposedFileChange(
                path=str(relative_path).replace("\\", "/"),
                additions=additions,
                deletions=deletions,
                is_binary=False,
            )
        )
        updated_result = _append_event(
            updated_result,
            event_type="file.written",
            status="succeeded",
            payload={"path": str(relative_path).replace("\\", "/")},
        )

    for patch in plan.patches:
        relative_path = _normalize_relative_path(patch.path)
        absolute_path = repo_root / relative_path
        if not absolute_path.exists():
            raise RuntimeConfigError(
                f"autonomous patch target does not exist: {str(relative_path).replace('\\', '/')}"
            )
        before_content = absolute_path.read_text()
        match_count = before_content.count(patch.before)
        if match_count == 0:
            raise RuntimeConfigError(
                f"autonomous patch target did not contain the expected text: {str(relative_path).replace('\\', '/')}"
            )
        if match_count > 1:
            raise RuntimeConfigError(
                f"autonomous patch target matched multiple locations and is ambiguous: {str(relative_path).replace('\\', '/')}"
            )
        after_content = before_content.replace(patch.before, patch.after, 1)
        absolute_path.write_text(after_content)
        if before_content == after_content:
            continue
        additions, deletions = _line_diff_stats(before_content, after_content)
        changed_files.append(
            ProposedFileChange(
                path=str(relative_path).replace("\\", "/"),
                additions=additions,
                deletions=deletions,
                is_binary=False,
            )
        )
        updated_result = _append_event(
            updated_result,
            event_type="file.patched",
            status="succeeded",
            payload={
                "path": str(relative_path).replace("\\", "/"),
                "mode": "exact_replace",
            },
        )

    return tuple(changed_files), updated_result


def _line_diff_stats(before: str, after: str) -> tuple[int, int]:
    additions = 0
    deletions = 0
    for line in difflib.ndiff(before.splitlines(), after.splitlines()):
        if line.startswith("+ "):
            additions += 1
        elif line.startswith("- "):
            deletions += 1
    return additions, deletions


def _run_validation_commands(
    *,
    repo_root: Path,
    commands: tuple[str, ...],
    execution_result: ProviderExecutionResult,
) -> tuple[tuple[ValidationCommandResult, ...], ProviderExecutionResult]:
    results: list[ValidationCommandResult] = []
    updated_result = execution_result
    for command in commands:
        updated_result = _append_event(
            updated_result,
            event_type="command.started",
            status="started",
            payload={"command": command},
        )
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        result = ValidationCommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        results.append(result)
        updated_result = _append_event(
            updated_result,
            event_type="command.completed",
            status="succeeded" if result.passed else "failed",
            payload={
                "command": command,
                "exit_code": result.exit_code,
                "stdout_preview": result.stdout[:200],
                "stderr_preview": result.stderr[:200],
            },
        )
    return tuple(results), updated_result


def _render_validation_summary(results: tuple[ValidationCommandResult, ...]) -> str:
    if not results:
        return "no validation commands were executed"
    parts = []
    for result in results:
        status = "passed" if result.passed else f"failed({result.exit_code})"
        preview = (result.stdout or result.stderr).strip().splitlines()
        preview_text = preview[0] if preview else "no output"
        parts.append(f"{result.command}: {status} - {preview_text[:120]}")
    return " | ".join(parts)


def _evaluate_autonomous_write_request(
    *,
    ticket: TicketRecord,
    execution_result: ProviderExecutionResult,
    changed_files: tuple[ProposedFileChange, ...],
    validation_summary: str,
    validation_passed: bool,
    write_policy_path: Path,
) -> ValidationDecision:
    if execution_result.status != "succeeded":
        return ValidationDecision(
            decision="rejected",
            reason=execution_result.attempt_summary.get("error", {}).get("kind", "executor_failed"),
            diagnostics=(str(execution_result.attempt_summary.get("error", {}).get("message", "executor failed")),),
            changed_paths=tuple(change.path for change in changed_files),
            requires_human_review=False,
        )

    return evaluate_write_request(
        ValidationInput(
            ticket_id=ticket.id,
            run_id=execution_result.attempt_summary["run_id"],
            attempt_id=execution_result.attempt_summary["attempt_id"],
            executor_status=execution_result.status,
            output_text=execution_result.output_text,
            changed_files=changed_files,
            validation_summary=validation_summary,
            validation_passed=validation_passed,
            usage=execution_result.usage,
        ),
        load_write_policy(write_policy_path),
    )


def _with_runtime_validation_events(
    execution_result: ProviderExecutionResult,
    *,
    validation_decision: ValidationDecision,
    validation_summary: str,
) -> ProviderExecutionResult:
    updated = _append_event(
        execution_result,
        event_type="validation.completed",
        status="succeeded" if validation_decision.decision == "accepted" else "failed",
        payload={
            "decision": validation_decision.decision,
            "reason": validation_decision.reason,
            "summary": validation_summary,
            "diagnostics": list(validation_decision.diagnostics),
        },
    )
    return _append_event(
        updated,
        event_type="write_gate.decided",
        status="succeeded" if validation_decision.decision == "accepted" else "failed",
        payload={
            "decision": validation_decision.decision,
            "reason": validation_decision.reason,
            "changed_paths": list(validation_decision.changed_paths),
        },
    )


def _append_event(
    execution_result: ProviderExecutionResult,
    *,
    event_type: str,
    status: str,
    payload: dict[str, object] | None = None,
    error: dict[str, object] | None = None,
) -> ProviderExecutionResult:
    events = list(execution_result.events)
    builder = EventStreamBuilder(
        run_id=execution_result.attempt_summary["run_id"],
        attempt_id=execution_result.attempt_summary["attempt_id"],
        ticket_id=execution_result.attempt_summary["ticket_id"],
        executor_version="phase-6",
    )
    builder._sequence = len(events)
    builder.append(event_type, status, payload=payload, error=error)
    events.extend(builder.build())
    return replace(execution_result, events=tuple(events))


def _mark_execution_failed(
    execution_result: ProviderExecutionResult,
    *,
    error_kind: str,
    message: str,
) -> ProviderExecutionResult:
    error = {"kind": error_kind, "message": message, "retryable": False}
    updated_summary = dict(execution_result.attempt_summary)
    updated_summary["final_result"] = "failed"
    updated_summary["error"] = error
    updated_result = replace(
        execution_result,
        status="failed",
        attempt_summary=updated_summary,
    )
    return _append_event(
        updated_result,
        event_type="command.completed",
        status="failed",
        payload={"phase": "autonomous_materialization", "message": message},
        error=error,
    )


def _normalize_relative_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        raise RuntimeConfigError(f"autonomous response path must be relative: {path_text}")
    if any(part == ".." for part in path.parts):
        raise RuntimeConfigError(f"autonomous response path must not escape repo root: {path_text}")
    if not path.parts:
        raise RuntimeConfigError("autonomous response path must not be empty")
    return path


def _default_muontickets_cli(repo_root: Path) -> Path:
    return repo_root / "tickets" / "mt" / "muontickets" / "muontickets" / "mt.py"


def _require_file_exists(path: Path, *, flag_name: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{flag_name} path not found: {path}")
    if not path.is_file():
        raise ValueError(f"{flag_name} must be a file: {path}")
    return path


def _run_muontickets_command(mt_cli_path: Path, args: Iterable[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        [sys.executable, str(mt_cli_path), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeConfigError(f"MuonTickets command failed: {detail or 'unknown error'}")
    return completed.stdout.strip()
