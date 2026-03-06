"""Validated benchmark workload manifest loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


_ALLOWED_WORK_TYPES = {"code", "refactor", "tests", "docs", "chore", "spec"}
_ALLOWED_PRIORITIES = {"p0", "p1", "p2"}
_ALLOWED_PLATFORMS = {
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
_ALLOWED_COMPLEXITIES = {"low", "medium", "high"}
_ALLOWED_EXECUTION_TARGETS = {"auto", "hosted", "local"}
_ALLOWED_TOOL_PROFILES = {"none", "standard", "extended"}
_FORBIDDEN_KEYS = {
    "api_key",
    "authorization",
    "bearer_token",
    "cookie",
    "env",
    "headers",
    "private_key",
    "provider_payload",
    "raw_prompt",
    "raw_response",
    "response",
    "secret",
    "stderr",
    "stdout",
    "token",
}
_ALLOWED_MANIFEST_KEYS = {"schema_version", "workloads"}
_ALLOWED_WORKLOAD_KEYS = {
    "id",
    "title",
    "description",
    "task",
    "ticket_shape",
    "success_criteria",
    "tags",
    "requires_repository_write",
}
_ALLOWED_TICKET_SHAPE_KEYS = {
    "work_type",
    "priority",
    "platform",
    "complexity",
    "execution_target",
    "tool_profile",
    "labels",
    "tags",
}


class BenchmarkManifestError(ValueError):
    """Raised when a benchmark manifest is malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class BenchmarkTicketShape:
    """Comparable ticket-shape inputs for one benchmark workload."""

    work_type: str
    priority: str
    platform: str
    complexity: str
    execution_target: str
    tool_profile: str
    labels: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BenchmarkWorkload:
    """Reusable benchmark workload safe for deterministic comparison."""

    workload_id: str
    title: str
    description: str
    task: str
    ticket_shape: BenchmarkTicketShape
    success_criteria: tuple[str, ...]
    tags: tuple[str, ...] = ()
    requires_repository_write: bool = False


@dataclass(frozen=True, slots=True)
class BenchmarkWorkloadManifest:
    """Loaded benchmark workload corpus and schema version."""

    schema_version: int
    workloads: tuple[BenchmarkWorkload, ...]


def default_benchmark_manifest_path() -> Path:
    return Path(__file__).with_name("fixtures") / "workloads.yaml"


def load_benchmark_workload_manifest(
    path: Path | None = None,
) -> BenchmarkWorkloadManifest:
    """Load the benchmark workload manifest from disk."""

    manifest_path = path or default_benchmark_manifest_path()
    payload = yaml.safe_load(manifest_path.read_text())
    if not isinstance(payload, dict):
        raise BenchmarkManifestError("benchmark manifest must be a mapping")

    _reject_unknown_or_forbidden_keys(payload, _ALLOWED_MANIFEST_KEYS, context="manifest")
    schema_version = payload.get("schema_version")
    if schema_version != 1:
        raise BenchmarkManifestError("benchmark manifest schema_version must be 1")

    raw_workloads = payload.get("workloads")
    if not isinstance(raw_workloads, list) or not raw_workloads:
        raise BenchmarkManifestError("benchmark manifest workloads must be a non-empty list")

    workloads = tuple(_build_workload(index, item) for index, item in enumerate(raw_workloads))
    workload_ids = [workload.workload_id for workload in workloads]
    if len(set(workload_ids)) != len(workload_ids):
        raise BenchmarkManifestError("benchmark manifest workload ids must be unique")

    return BenchmarkWorkloadManifest(schema_version=1, workloads=workloads)


def _build_workload(index: int, payload: object) -> BenchmarkWorkload:
    if not isinstance(payload, dict):
        raise BenchmarkManifestError(f"workload[{index}] must be a mapping")

    _reject_unknown_or_forbidden_keys(payload, _ALLOWED_WORKLOAD_KEYS, context=f"workload[{index}]")
    ticket_shape_payload = _require_mapping(payload, "ticket_shape", context=f"workload[{index}]")
    return BenchmarkWorkload(
        workload_id=_require_string(payload, "id", context=f"workload[{index}]"),
        title=_require_string(payload, "title", context=f"workload[{index}]"),
        description=_require_string(payload, "description", context=f"workload[{index}]"),
        task=_require_string(payload, "task", context=f"workload[{index}]"),
        ticket_shape=_build_ticket_shape(ticket_shape_payload, context=f"workload[{index}].ticket_shape"),
        success_criteria=_require_string_list(
            payload,
            "success_criteria",
            context=f"workload[{index}]",
            min_items=1,
        ),
        tags=_require_string_list(payload, "tags", context=f"workload[{index}]"),
        requires_repository_write=_require_bool(
            payload,
            "requires_repository_write",
            context=f"workload[{index}]",
        ),
    )


def _build_ticket_shape(payload: Mapping[str, Any], *, context: str) -> BenchmarkTicketShape:
    _reject_unknown_or_forbidden_keys(payload, _ALLOWED_TICKET_SHAPE_KEYS, context=context)
    work_type = _require_string(payload, "work_type", context=context)
    priority = _require_string(payload, "priority", context=context)
    platform = _require_string(payload, "platform", context=context)
    complexity = _require_string(payload, "complexity", context=context)
    execution_target = _require_string(payload, "execution_target", context=context)
    tool_profile = _require_string(payload, "tool_profile", context=context)

    _require_allowed_value(work_type, _ALLOWED_WORK_TYPES, field_name="work_type", context=context)
    _require_allowed_value(priority, _ALLOWED_PRIORITIES, field_name="priority", context=context)
    _require_allowed_value(platform, _ALLOWED_PLATFORMS, field_name="platform", context=context)
    _require_allowed_value(complexity, _ALLOWED_COMPLEXITIES, field_name="complexity", context=context)
    _require_allowed_value(
        execution_target,
        _ALLOWED_EXECUTION_TARGETS,
        field_name="execution_target",
        context=context,
    )
    _require_allowed_value(
        tool_profile,
        _ALLOWED_TOOL_PROFILES,
        field_name="tool_profile",
        context=context,
    )

    return BenchmarkTicketShape(
        work_type=work_type,
        priority=priority,
        platform=platform,
        complexity=complexity,
        execution_target=execution_target,
        tool_profile=tool_profile,
        labels=_require_string_list(payload, "labels", context=context),
        tags=_require_string_list(payload, "tags", context=context),
    )


def _reject_unknown_or_forbidden_keys(
    payload: Mapping[str, Any],
    allowed_keys: set[str],
    *,
    context: str,
) -> None:
    keys = set(payload)
    forbidden_keys = sorted(key for key in keys if str(key) in _FORBIDDEN_KEYS)
    if forbidden_keys:
        raise BenchmarkManifestError(
            f"{context} contains forbidden secret-bearing keys: {', '.join(forbidden_keys)}"
        )

    unknown_keys = sorted(str(key) for key in keys if str(key) not in allowed_keys)
    if unknown_keys:
        raise BenchmarkManifestError(f"{context} contains unsupported keys: {', '.join(unknown_keys)}")


def _require_mapping(payload: Mapping[str, Any], key: str, *, context: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise BenchmarkManifestError(f"{context}.{key} must be a mapping")
    return value


def _require_string(payload: Mapping[str, Any], key: str, *, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkManifestError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _require_string_list(
    payload: Mapping[str, Any],
    key: str,
    *,
    context: str,
    min_items: int = 0,
) -> tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise BenchmarkManifestError(f"{context}.{key} must be a list of strings")
    items = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise BenchmarkManifestError(f"{context}.{key}[{index}] must be a non-empty string")
        items.append(item.strip())
    if len(items) < min_items:
        raise BenchmarkManifestError(f"{context}.{key} must contain at least {min_items} item(s)")
    return tuple(items)


def _require_bool(payload: Mapping[str, Any], key: str, *, context: str) -> bool:
    value = payload.get(key, False)
    if not isinstance(value, bool):
        raise BenchmarkManifestError(f"{context}.{key} must be a boolean")
    return value


def _require_allowed_value(
    value: str,
    allowed_values: set[str],
    *,
    field_name: str,
    context: str,
) -> None:
    if value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise BenchmarkManifestError(
            f"{context}.{field_name} must be one of: {allowed}"
        )