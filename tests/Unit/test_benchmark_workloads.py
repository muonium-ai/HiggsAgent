from __future__ import annotations

from pathlib import Path

import pytest

from higgs_agent.benchmarking import (
    BenchmarkManifestError,
    default_benchmark_manifest_path,
    load_benchmark_workload_manifest,
)


def test_default_benchmark_manifest_loads_expected_workloads() -> None:
    manifest = load_benchmark_workload_manifest()

    assert manifest.schema_version == 1
    assert [workload.workload_id for workload in manifest.workloads] == [
        "docs-release-notes-summary",
        "spec-routing-tradeoff-analysis",
        "tests-failure-triage-plan",
    ]
    assert all(workload.requires_repository_write is False for workload in manifest.workloads)
    assert all(workload.success_criteria for workload in manifest.workloads)


def test_default_benchmark_manifest_path_exists() -> None:
    manifest_path = default_benchmark_manifest_path()

    assert manifest_path.as_posix().endswith("src/higgs_agent/benchmarking/fixtures/workloads.yaml")
    assert manifest_path.exists()


def test_manifest_rejects_secret_bearing_or_unsupported_fields(tmp_path: Path) -> None:
    manifest_path = tmp_path / "workloads.yaml"
    manifest_path.write_text(
        "schema_version: 1\n"
        "workloads:\n"
        "  - id: unsafe\n"
        "    title: Unsafe\n"
        "    description: bad\n"
        "    task: test\n"
        "    api_key: secret\n"
        "    ticket_shape:\n"
        "      work_type: docs\n"
        "      priority: p2\n"
        "      platform: agnostic\n"
        "      complexity: low\n"
        "      execution_target: auto\n"
        "      tool_profile: none\n"
        "    success_criteria:\n"
        "      - keep safe\n"
    )

    with pytest.raises(BenchmarkManifestError, match="forbidden secret-bearing keys"):
        load_benchmark_workload_manifest(manifest_path)


def test_manifest_rejects_invalid_ticket_shape_values(tmp_path: Path) -> None:
    manifest_path = tmp_path / "workloads.yaml"
    manifest_path.write_text(
        "schema_version: 1\n"
        "workloads:\n"
        "  - id: invalid-shape\n"
        "    title: Invalid Shape\n"
        "    description: bad\n"
        "    task: test\n"
        "    ticket_shape:\n"
        "      work_type: unknown\n"
        "      priority: p2\n"
        "      platform: agnostic\n"
        "      complexity: low\n"
        "      execution_target: auto\n"
        "      tool_profile: none\n"
        "    success_criteria:\n"
        "      - keep safe\n"
    )

    with pytest.raises(BenchmarkManifestError, match="work_type must be one of"):
        load_benchmark_workload_manifest(manifest_path)
