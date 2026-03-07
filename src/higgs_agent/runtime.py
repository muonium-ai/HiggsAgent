"""First-party runtime helpers for executing a ticketed project workflow."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from higgs_agent.application import DispatchOutcome, dispatch_next_ready_ticket
from higgs_agent.events.records import utc_now_iso
from higgs_agent.providers.hosted import OpenRouterHTTPTransport
from higgs_agent.providers.contract import ExecutorArtifactRef
from higgs_agent.validation import ProposedFileChange


class RuntimeConfigError(ValueError):
    """Raised when runtime inputs are invalid or incomplete."""


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
