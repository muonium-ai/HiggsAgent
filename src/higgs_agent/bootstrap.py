"""Bootstrap helpers for sample-project evaluation repositories."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class BootstrapError(ValueError):
    """Raised when bootstrap inputs or filesystem state are invalid."""


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Summary of a completed sample-project bootstrap run."""

    target_dir: Path
    sample_project_dir: Path
    higgsagent_submodule_dir: Path


def bootstrap_sample_project(
    *,
    target_dir: Path,
    sample_project: str,
    higgsagent_repo_url: str,
    force: bool = False,
    source_repo_root: Path | None = None,
    python_executable: str | None = None,
) -> BootstrapResult:
    """Create a fresh evaluation repository for a shipped sample project."""

    repo_root = source_repo_root or _default_source_repo_root()
    sample_source_dir = repo_root / "sample-projects" / sample_project
    if not sample_source_dir.is_dir():
        raise BootstrapError(f"unknown sample project: {sample_project}")

    _ensure_target_dir(target_dir, force=force)
    _initialize_git_repo(target_dir)
    _copy_sample_project_tree(sample_source_dir, target_dir / "sample-projects" / sample_project, force=force)
    _copy_env_example(repo_root / ".env.example", target_dir / ".env.example", force=force)
    _create_local_layout(target_dir)

    submodule_dir = target_dir / "tools" / "higgsagent"
    _add_higgsagent_submodule(target_dir, submodule_dir, higgsagent_repo_url=higgsagent_repo_url)
    _update_higgsagent_submodules(submodule_dir)
    _validate_sample_project_board(
        target_dir / "sample-projects" / sample_project,
        python_executable=python_executable or sys.executable,
    )

    return BootstrapResult(
        target_dir=target_dir,
        sample_project_dir=target_dir / "sample-projects" / sample_project,
        higgsagent_submodule_dir=submodule_dir,
    )


def available_sample_projects(source_repo_root: Path | None = None) -> tuple[str, ...]:
    root = source_repo_root or _default_source_repo_root()
    sample_projects_dir = root / "sample-projects"
    if not sample_projects_dir.is_dir():
        return ()
    return tuple(sorted(path.name for path in sample_projects_dir.iterdir() if path.is_dir()))


def _default_source_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_target_dir(target_dir: Path, *, force: bool) -> None:
    if target_dir.exists() and target_dir.is_file():
        raise BootstrapError(f"target path is a file: {target_dir}")
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        raise BootstrapError(f"target directory is not empty: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)


def _initialize_git_repo(target_dir: Path) -> None:
    if (target_dir / ".git").exists():
        return
    _run_command(["git", "init"], cwd=target_dir)


def _copy_sample_project_tree(source_dir: Path, destination_dir: Path, *, force: bool) -> None:
    if destination_dir.exists() and not force:
        raise BootstrapError(f"sample project already exists at target path: {destination_dir}")
    shutil.copytree(source_dir, destination_dir, dirs_exist_ok=force)


def _copy_env_example(source_path: Path, destination_path: Path, *, force: bool) -> None:
    if not source_path.is_file():
        return
    if destination_path.exists() and not force:
        return
    shutil.copyfile(source_path, destination_path)


def _create_local_layout(target_dir: Path) -> None:
    (target_dir / "bin").mkdir(parents=True, exist_ok=True)
    (target_dir / "tools").mkdir(parents=True, exist_ok=True)
    (target_dir / ".higgs" / "local" / "runs").mkdir(parents=True, exist_ok=True)
    (target_dir / ".higgs" / "local" / "analytics").mkdir(parents=True, exist_ok=True)


def _add_higgsagent_submodule(target_dir: Path, submodule_dir: Path, *, higgsagent_repo_url: str) -> None:
    if submodule_dir.exists():
        return
    _run_command(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            higgsagent_repo_url,
            "tools/higgsagent",
        ],
        cwd=target_dir,
    )


def _update_higgsagent_submodules(submodule_dir: Path) -> None:
    _run_command(["git", "submodule", "update", "--init", "--recursive"], cwd=submodule_dir)


def _validate_sample_project_board(sample_project_dir: Path, *, python_executable: str) -> None:
    mt_path = sample_project_dir.parent.parent / "tools" / "higgsagent" / "tickets" / "mt" / "muontickets" / "mt.py"
    if not mt_path.is_file():
        raise BootstrapError(f"MuonTickets CLI not found after submodule setup: {mt_path}")
    _run_command([python_executable, str(mt_path), "validate"], cwd=sample_project_dir)


def _run_command(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        details = stderr or stdout or f"command failed: {' '.join(command)}"
        raise BootstrapError(details)
