"""Unit tests for benchmark workload manifest loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from higgs_agent.benchmarking.workloads import (
    BenchmarkManifestError,
    BenchmarkWorkloadManifest,
    load_benchmark_workload_manifest,
)


def _minimal_workload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "wl-001",
        "title": "Test workload",
        "description": "A test workload",
        "task": "Do a thing",
        "ticket_shape": {
            "work_type": "code",
            "priority": "p1",
            "platform": "agnostic",
            "complexity": "low",
            "execution_target": "auto",
            "tool_profile": "none",
        },
        "success_criteria": ["criteria-1"],
        "tags": [],
        "requires_repository_write": False,
    }
    base.update(overrides)
    return base


def _write_manifest(tmp_path: Path, workloads: list[dict[str, object]]) -> Path:
    manifest_path = tmp_path / "workloads.yaml"
    manifest_path.write_text(
        yaml.dump({"schema_version": 1, "workloads": workloads})
    )
    return manifest_path


def test_load_valid_manifest(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, [_minimal_workload()])
    manifest = load_benchmark_workload_manifest(path)
    assert isinstance(manifest, BenchmarkWorkloadManifest)
    assert manifest.schema_version == 1
    assert len(manifest.workloads) == 1
    assert manifest.workloads[0].workload_id == "wl-001"


def test_rejects_non_mapping_manifest(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- a list")
    with pytest.raises(BenchmarkManifestError, match="must be a mapping"):
        load_benchmark_workload_manifest(path)


def test_rejects_wrong_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.dump({"schema_version": 2, "workloads": []}))
    with pytest.raises(BenchmarkManifestError, match="schema_version must be 1"):
        load_benchmark_workload_manifest(path)


def test_rejects_empty_workloads(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.dump({"schema_version": 1, "workloads": []}))
    with pytest.raises(BenchmarkManifestError, match="non-empty list"):
        load_benchmark_workload_manifest(path)


def test_rejects_duplicate_workload_ids(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        [_minimal_workload(id="dup"), _minimal_workload(id="dup", title="Second")],
    )
    with pytest.raises(BenchmarkManifestError, match="unique"):
        load_benchmark_workload_manifest(path)


def test_rejects_forbidden_keys(tmp_path: Path) -> None:
    wl = _minimal_workload()
    wl["secret"] = "oops"
    path = _write_manifest(tmp_path, [wl])
    with pytest.raises(BenchmarkManifestError, match="forbidden"):
        load_benchmark_workload_manifest(path)


def test_rejects_unknown_manifest_keys(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.dump({"schema_version": 1, "workloads": [_minimal_workload()], "extra": 1})
    )
    with pytest.raises(BenchmarkManifestError, match="unsupported keys"):
        load_benchmark_workload_manifest(path)


def test_rejects_invalid_work_type(tmp_path: Path) -> None:
    wl = _minimal_workload()
    assert isinstance(wl["ticket_shape"], dict)
    wl["ticket_shape"]["work_type"] = "invalid"
    path = _write_manifest(tmp_path, [wl])
    with pytest.raises(BenchmarkManifestError, match="work_type must be one of"):
        load_benchmark_workload_manifest(path)


def test_rejects_missing_required_string(tmp_path: Path) -> None:
    wl = _minimal_workload()
    del wl["title"]
    path = _write_manifest(tmp_path, [wl])
    with pytest.raises(BenchmarkManifestError, match="title must be a non-empty string"):
        load_benchmark_workload_manifest(path)


def test_ticket_shape_labels_and_tags(tmp_path: Path) -> None:
    wl = _minimal_workload()
    assert isinstance(wl["ticket_shape"], dict)
    wl["ticket_shape"]["labels"] = ["lbl-1"]
    wl["ticket_shape"]["tags"] = ["tag-1", "tag-2"]
    path = _write_manifest(tmp_path, [wl])
    manifest = load_benchmark_workload_manifest(path)
    shape = manifest.workloads[0].ticket_shape
    assert shape.labels == ("lbl-1",)
    assert shape.tags == ("tag-1", "tag-2")
