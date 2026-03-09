"""Unit tests for bootstrap helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from higgs_agent.bootstrap import (
    BootstrapError,
    _copy_env_example,
    _copy_sample_project_tree,
    _create_local_layout,
    _ensure_target_dir,
    _run_command,
    available_sample_projects,
)


def test_ensure_target_dir_creates_missing_directory(tmp_path: Path) -> None:
    target = tmp_path / "new_dir"
    _ensure_target_dir(target, force=False)
    assert target.is_dir()


def test_ensure_target_dir_raises_when_target_is_file(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("content")
    with pytest.raises(BootstrapError, match="target path is a file"):
        _ensure_target_dir(target, force=False)


def test_ensure_target_dir_raises_when_not_empty_without_force(
    tmp_path: Path,
) -> None:
    (tmp_path / "existing.txt").write_text("x")
    with pytest.raises(BootstrapError, match="not empty"):
        _ensure_target_dir(tmp_path, force=False)


def test_ensure_target_dir_allows_non_empty_with_force(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("x")
    _ensure_target_dir(tmp_path, force=True)
    assert tmp_path.is_dir()


def test_copy_sample_project_tree_copies_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.py").write_text("print('hello')")
    dest = tmp_path / "dest"
    _copy_sample_project_tree(source, dest, force=False)
    assert (dest / "file.py").read_text() == "print('hello')"


def test_copy_sample_project_tree_raises_when_exists_without_force(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(BootstrapError, match="already exists"):
        _copy_sample_project_tree(source, dest, force=False)


def test_copy_env_example_copies_when_source_exists(tmp_path: Path) -> None:
    source = tmp_path / ".env.example"
    source.write_text("KEY=value")
    dest = tmp_path / "target" / ".env.example"
    dest.parent.mkdir()
    _copy_env_example(source, dest, force=False)
    assert dest.read_text() == "KEY=value"


def test_copy_env_example_skips_when_source_missing(tmp_path: Path) -> None:
    source = tmp_path / ".env.example"
    dest = tmp_path / "target" / ".env.example"
    _copy_env_example(source, dest, force=False)
    assert not dest.exists()


def test_copy_env_example_skips_when_dest_exists_without_force(
    tmp_path: Path,
) -> None:
    source = tmp_path / ".env.example"
    source.write_text("NEW=value")
    dest = tmp_path / "dest.env"
    dest.write_text("OLD=value")
    _copy_env_example(source, dest, force=False)
    assert dest.read_text() == "OLD=value"


def test_create_local_layout_creates_expected_directories(
    tmp_path: Path,
) -> None:
    _create_local_layout(tmp_path)
    assert (tmp_path / "bin").is_dir()
    assert (tmp_path / "tools").is_dir()
    assert (tmp_path / ".higgs" / "local" / "runs").is_dir()
    assert (tmp_path / ".higgs" / "local" / "analytics").is_dir()


def test_available_sample_projects_returns_empty_for_missing_dir(
    tmp_path: Path,
) -> None:
    assert available_sample_projects(tmp_path) == ()


def test_available_sample_projects_lists_subdirectories(
    tmp_path: Path,
) -> None:
    sp_dir = tmp_path / "sample-projects"
    sp_dir.mkdir()
    (sp_dir / "game-of-life").mkdir()
    (sp_dir / "calculator").mkdir()
    (sp_dir / "README.md").write_text("ignore me")
    result = available_sample_projects(tmp_path)
    assert result == ("calculator", "game-of-life")


def test_run_command_raises_on_failure(tmp_path: Path) -> None:
    with pytest.raises(BootstrapError):
        _run_command(["false"], cwd=tmp_path)
