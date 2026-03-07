"""Validation boundary for repository writes and review handoff decisions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from higgs_agent.providers.contract import ProviderUsage

SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+[a-z0-9._\-]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[a-z0-9_\-/+=]{8,}"),
)
PROTECTED_NAME_PATTERNS = (".env*", "*.pem", "*.key")


class WritePolicyError(ValueError):
    """Raised when write-policy configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ProposedFileChange:
    """Normalized repository mutation proposed by the executor output."""

    path: str
    additions: int = 0
    deletions: int = 0
    is_binary: bool = False

    @property
    def net_line_delta(self) -> int:
        return self.additions + self.deletions


@dataclass(frozen=True, slots=True)
class WritePolicy:
    """Policy constraints controlling repository mutation and review handoff."""

    allowed_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]
    max_changed_files: int
    max_net_line_delta: int
    allow_binary_writes: bool
    require_human_review_on_protected_path: bool
    require_human_review_on_secret_suspect: bool
    require_human_review_on_policy_violation: bool


@dataclass(frozen=True, slots=True)
class ValidationInput:
    """Data required to decide whether executor output may be persisted."""

    ticket_id: str
    run_id: str
    attempt_id: str
    executor_status: str
    output_text: str
    changed_files: tuple[ProposedFileChange, ...]
    validation_summary: str
    validation_passed: bool = True
    usage: ProviderUsage | None = None
    diff_is_deterministic: bool = True


@dataclass(frozen=True, slots=True)
class ValidationDecision:
    """Outcome of the write gate."""

    decision: str
    reason: str
    diagnostics: tuple[str, ...]
    changed_paths: tuple[str, ...]
    requires_human_review: bool
    handoff_message: str | None = None


def load_write_policy(config_path: Path) -> WritePolicy:
    """Load and validate write-policy configuration."""

    payload = json.loads(config_path.read_text())
    allowed_paths = _require_string_list(payload, "allowed_paths")
    protected_paths = _require_string_list(payload, "protected_paths")

    limits = payload.get("limits")
    if not isinstance(limits, dict):
        raise WritePolicyError("write policy missing 'limits' object")

    handoff = payload.get("handoff")
    if not isinstance(handoff, dict):
        raise WritePolicyError("write policy missing 'handoff' object")

    return WritePolicy(
        allowed_paths=tuple(allowed_paths),
        protected_paths=tuple(protected_paths),
        max_changed_files=_require_int(limits, "max_changed_files"),
        max_net_line_delta=_require_int(limits, "max_net_line_delta"),
        allow_binary_writes=_require_bool(limits, "allow_binary_writes"),
        require_human_review_on_protected_path=_require_bool(
            handoff, "require_human_review_on_protected_path"
        ),
        require_human_review_on_secret_suspect=_require_bool(
            handoff, "require_human_review_on_secret_suspect"
        ),
        require_human_review_on_policy_violation=_require_bool(
            handoff, "require_human_review_on_policy_violation"
        ),
    )


def evaluate_write_request(
    validation_input: ValidationInput,
    policy: WritePolicy,
) -> ValidationDecision:
    """Decide whether output may be persisted, requires handoff, or must be rejected."""

    diagnostics: list[str] = []
    changed_paths = tuple(change.path for change in validation_input.changed_files)

    if validation_input.executor_status != "succeeded":
        diagnostics.append(f"executor_status:{validation_input.executor_status}")
        return ValidationDecision(
            decision="rejected",
            reason="executor_did_not_succeed",
            diagnostics=tuple(diagnostics),
            changed_paths=changed_paths,
            requires_human_review=False,
        )

    if not validation_input.validation_passed:
        diagnostics.append("validation_failed")
        return ValidationDecision(
            decision="rejected",
            reason="validation_failed",
            diagnostics=tuple(diagnostics),
            changed_paths=changed_paths,
            requires_human_review=False,
        )

    if not validation_input.changed_files:
        diagnostics.append("no_changed_files")
        return ValidationDecision(
            decision="rejected",
            reason="no_repository_mutation_proposed",
            diagnostics=tuple(diagnostics),
            changed_paths=changed_paths,
            requires_human_review=False,
        )

    protected_hits = [
        path for path in changed_paths if _matches_any(path, policy.protected_paths)
    ]
    disallowed_hits = [
        path for path in changed_paths if not _matches_any(path, policy.allowed_paths)
    ]
    binary_hits = [change.path for change in validation_input.changed_files if change.is_binary]

    if len(validation_input.changed_files) > policy.max_changed_files:
        diagnostics.append(
            f"max_changed_files_exceeded:{len(validation_input.changed_files)}>{policy.max_changed_files}"
        )

    total_net_delta = sum(change.net_line_delta for change in validation_input.changed_files)
    if total_net_delta > policy.max_net_line_delta:
        diagnostics.append(
            f"max_net_line_delta_exceeded:{total_net_delta}>{policy.max_net_line_delta}"
        )

    if disallowed_hits:
        diagnostics.append(f"disallowed_paths:{', '.join(disallowed_hits)}")

    if binary_hits and not policy.allow_binary_writes:
        diagnostics.append(f"binary_writes_not_allowed:{', '.join(binary_hits)}")

    secret_suspect = _detect_secret_suspect(validation_input.output_text, changed_paths)
    if secret_suspect:
        diagnostics.append("secret_suspect_detected")

    if not validation_input.diff_is_deterministic:
        diagnostics.append("diff_is_not_deterministic")

    if protected_hits:
        diagnostics.append(f"protected_paths:{', '.join(protected_hits)}")

    requires_review = False
    if protected_hits and policy.require_human_review_on_protected_path:
        requires_review = True
    if secret_suspect and policy.require_human_review_on_secret_suspect:
        requires_review = True
    if diagnostics and policy.require_human_review_on_policy_violation:
        requires_review = True

    if requires_review:
        return ValidationDecision(
            decision="handoff_required",
            reason=_primary_reason(diagnostics, protected_hits, secret_suspect),
            diagnostics=tuple(diagnostics),
            changed_paths=changed_paths,
            requires_human_review=True,
            handoff_message=render_review_handoff(validation_input, diagnostics, changed_paths),
        )

    if diagnostics:
        return ValidationDecision(
            decision="rejected",
            reason=_primary_reason(diagnostics, protected_hits, secret_suspect),
            diagnostics=tuple(diagnostics),
            changed_paths=changed_paths,
            requires_human_review=False,
        )

    return ValidationDecision(
        decision="accepted",
        reason="write_request_within_policy",
        diagnostics=(),
        changed_paths=changed_paths,
        requires_human_review=False,
    )


def render_review_handoff(
    validation_input: ValidationInput,
    diagnostics: list[str] | tuple[str, ...],
    changed_paths: tuple[str, ...],
) -> str:
    """Render a human-review handoff message using the agreed template fields."""

    usage_summary = "unknown"
    if validation_input.usage is not None:
        usage_summary = (
            f"tokens {validation_input.usage.total_tokens or 0}"
            f", cost {validation_input.usage.cost_usd or 0:.2f}"
            f", latency {validation_input.usage.latency_ms or 0}ms"
        )

    return "\n".join(
        [
            f"Ticket ID: {validation_input.ticket_id}",
            f"Run ID: {validation_input.run_id}",
            f"Attempt ID: {validation_input.attempt_id}",
            f"Changed paths: {', '.join(changed_paths) if changed_paths else 'none'}",
            f"Validation summary: {validation_input.validation_summary}",
            f"Guardrail usage summary: {usage_summary}",
            f"Blocking reason: {diagnostics[0] if diagnostics else 'manual review required'}",
            (
                "Suggested next action: review the proposed changes and decide whether to "
                "approve, revise, or reject them"
            ),
        ]
    )


def _detect_secret_suspect(output_text: str, changed_paths: tuple[str, ...]) -> bool:
    if any(fnmatch(path, pattern) for path in changed_paths for pattern in PROTECTED_NAME_PATTERNS):
        return True
    return any(pattern.search(output_text) for pattern in SECRET_PATTERNS)


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def _primary_reason(
    diagnostics: list[str],
    protected_hits: list[str],
    secret_suspect: bool,
) -> str:
    if secret_suspect:
        return "secret_suspect"
    if protected_hits:
        return "protected_path_touched"
    if diagnostics:
        return diagnostics[0].split(":", 1)[0]
    return "validation_failed"


def _require_string_list(payload: dict[str, object], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise WritePolicyError(f"write policy missing valid '{field_name}' list")
    return value


def _require_int(payload: dict[str, object], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int):
        raise WritePolicyError(f"write policy missing valid '{field_name}'")
    return value


def _require_bool(payload: dict[str, object], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise WritePolicyError(f"write policy missing valid '{field_name}'")
    return value