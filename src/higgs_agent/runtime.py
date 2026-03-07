"""First-party runtime helpers for executing a ticketed project workflow."""

from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import uuid4

from higgs_agent.application import DispatchOutcome, dispatch_next_ready_ticket
from higgs_agent.providers.hosted import OpenRouterHTTPTransport
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
    return outcome


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
