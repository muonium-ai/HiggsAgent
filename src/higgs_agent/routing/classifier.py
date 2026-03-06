"""Normalize ticket metadata into deterministic Phase 1 routing semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast

from higgs_agent.tickets import TicketRecord

DEFAULT_EXECUTION_TARGET = "auto"
DEFAULT_PLATFORM = "agnostic"
DEFAULT_TOOL_PROFILE = "standard"
SUPPORTED_SCHEMA_VERSION = 1

ALLOWED_COMPLEXITIES = {"low", "medium", "high"}
ALLOWED_EXECUTION_TARGETS = {"auto", "hosted", "local"}
ALLOWED_PLATFORMS = {
    "agnostic",
    "web",
    "ios",
    "macos",
    "android",
    "linux",
    "windows",
    "cross_platform",
    "repo",
}
ALLOWED_PRIORITIES = {"p0", "p1", "p2"}
ALLOWED_TOOL_PROFILES = {"none", "standard", "extended"}
EFFORT_TO_COMPLEXITY = {"xs": "low", "s": "low", "m": "medium", "l": "high"}


class ClassificationInputError(ValueError):
    """Raised when ticket metadata cannot be normalized safely."""


@dataclass(frozen=True, slots=True)
class NormalizedTicketSemantics:
    """Deterministic classifier output consumed by the dispatcher router."""

    ticket_id: str
    work_type: str
    priority: str
    platform: str
    complexity: str
    execution_target: str
    tool_profile: str
    labels: tuple[str, ...]
    tags: tuple[str, ...]
    warnings: tuple[str, ...]


def classify_ticket(ticket: TicketRecord | Mapping[str, Any]) -> NormalizedTicketSemantics:
    """Normalize approved ticket metadata into Phase 1 routing semantics."""

    payload = _coerce_frontmatter(ticket)
    warnings: list[str] = []

    ticket_id = _require_string(payload, "id")
    work_type = _require_string(payload, "type")
    priority = _normalize_priority(payload, warnings)
    schema_version = _normalize_schema_version(payload, warnings)
    platform = _normalize_platform(payload, warnings)
    complexity = _normalize_complexity(payload, warnings)
    execution_target = _normalize_execution_target(payload)
    tool_profile = _normalize_tool_profile(payload)
    labels = _normalize_string_list(payload, "labels")
    tags = _normalize_string_list(payload, "tags")

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ClassificationInputError(
            f"ticket {ticket_id}: unsupported higgs_schema_version '{schema_version}'"
        )

    return NormalizedTicketSemantics(
        ticket_id=ticket_id,
        work_type=work_type,
        priority=priority,
        platform=platform,
        complexity=complexity,
        execution_target=execution_target,
        tool_profile=tool_profile,
        labels=labels,
        tags=tags,
        warnings=tuple(warnings),
    )


def _coerce_frontmatter(ticket: TicketRecord | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(ticket, TicketRecord):
        return ticket.frontmatter
    return ticket


def _require_string(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ClassificationInputError(f"missing or invalid '{field_name}' field")
    return value


def _normalize_priority(payload: Mapping[str, Any], warnings: list[str]) -> str:
    value = payload.get("priority")
    if value is None:
        warnings.append("priority missing; normalized to p2")
        return "p2"
    if not isinstance(value, str) or value not in ALLOWED_PRIORITIES:
        raise ClassificationInputError(f"invalid priority '{value}'")
    return value


def _normalize_schema_version(payload: Mapping[str, Any], warnings: list[str]) -> int:
    value = payload.get("higgs_schema_version")
    if value is None:
        warnings.append("higgs_schema_version missing; normalized to 1")
        return SUPPORTED_SCHEMA_VERSION
    if not isinstance(value, int):
        raise ClassificationInputError(f"invalid higgs_schema_version '{value}'")
    return value


def _normalize_platform(payload: Mapping[str, Any], warnings: list[str]) -> str:
    value = payload.get("higgs_platform")
    if value is None:
        warnings.append("higgs_platform missing; normalized to agnostic")
        return DEFAULT_PLATFORM
    if not isinstance(value, str) or value not in ALLOWED_PLATFORMS:
        raise ClassificationInputError(f"invalid higgs_platform '{value}'")
    return value


def _normalize_complexity(payload: Mapping[str, Any], warnings: list[str]) -> str:
    explicit_value = payload.get("higgs_complexity")
    if explicit_value is not None:
        if not isinstance(explicit_value, str) or explicit_value not in ALLOWED_COMPLEXITIES:
            raise ClassificationInputError(f"invalid higgs_complexity '{explicit_value}'")
        return explicit_value

    effort = payload.get("effort")
    if isinstance(effort, str) and effort in EFFORT_TO_COMPLEXITY:
        return EFFORT_TO_COMPLEXITY[effort]

    warnings.append("higgs_complexity missing; normalized to medium")
    return "medium"


def _normalize_execution_target(payload: Mapping[str, Any]) -> str:
    value = payload.get("higgs_execution_target", DEFAULT_EXECUTION_TARGET)
    if not isinstance(value, str) or value not in ALLOWED_EXECUTION_TARGETS:
        raise ClassificationInputError(f"invalid higgs_execution_target '{value}'")
    return value


def _normalize_tool_profile(payload: Mapping[str, Any]) -> str:
    value = payload.get("higgs_tool_profile", DEFAULT_TOOL_PROFILE)
    if not isinstance(value, str) or value not in ALLOWED_TOOL_PROFILES:
        raise ClassificationInputError(f"invalid higgs_tool_profile '{value}'")
    return value


def _normalize_string_list(payload: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    value = payload.get(field_name, [])
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ClassificationInputError(f"invalid {field_name} list")
    return tuple(cast(list[str], value))