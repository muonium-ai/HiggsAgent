from __future__ import annotations

from pathlib import Path

import pytest

from higgs_agent import bootstrap
from higgs_agent.cli import main


def test_bootstrap_sample_project_creates_layout_and_invokes_submodule_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_root = tmp_path / "source"
    sample_source = source_root / "sample-projects" / "game-of-life"
    (sample_source / "tickets").mkdir(parents=True)
    (sample_source / "requirements.md").write_text("requirements\n")
    (sample_source / "tickets" / "T-000002.md").write_text("---\nid: T-000002\n---\n")
    (sample_source / "tickets" / "last_ticket_id").write_text("T-000015\n")
    (sample_source / "tickets" / "ticket.template").write_text("template\n")
    (source_root / ".env.example").write_text("OPENROUTER_API_KEY=\n")

    calls: list[tuple[str, Path, str | None]] = []

    def fake_add(target_dir: Path, submodule_dir: Path, *, higgsagent_repo_url: str) -> None:
        calls.append(("add", target_dir, higgsagent_repo_url))
        (submodule_dir / "tickets" / "mt" / "muontickets").mkdir(parents=True, exist_ok=True)
        (submodule_dir / "tickets" / "mt" / "muontickets" / "mt.py").write_text("print('ok')\n")

    def fake_update(submodule_dir: Path) -> None:
        calls.append(("update", submodule_dir, None))

    def fake_validate(sample_project_dir: Path, *, python_executable: str) -> None:
        calls.append(("validate", sample_project_dir, python_executable))

    monkeypatch.setattr(bootstrap, "_default_source_repo_root", lambda: source_root)
    monkeypatch.setattr(bootstrap, "_add_higgsagent_submodule", fake_add)
    monkeypatch.setattr(bootstrap, "_update_higgsagent_submodules", fake_update)
    monkeypatch.setattr(bootstrap, "_validate_sample_project_board", fake_validate)

    target_dir = tmp_path / "evaluation-repo"
    main(["bootstrap", "sample-project", str(target_dir), "--higgsagent-repo-url", "https://example.invalid/HiggsAgent.git"])

    assert (target_dir / ".git").exists()
    assert (target_dir / "sample-projects" / "game-of-life" / "requirements.md").exists()
    assert (target_dir / ".env.example").exists()
    assert (target_dir / ".higgs" / "local" / "runs").is_dir()
    assert (target_dir / ".higgs" / "local" / "analytics").is_dir()
    assert calls[0][0] == "add"
    assert calls[1][0] == "update"
    assert calls[2][0] == "validate"
    assert "created evaluation repo" in capsys.readouterr().out


def test_bootstrap_sample_project_fails_for_nonempty_target_without_force(tmp_path: Path) -> None:
    target_dir = tmp_path / "evaluation-repo"
    target_dir.mkdir()
    (target_dir / "existing.txt").write_text("occupied\n")

    with pytest.raises(SystemExit, match=r"bootstrap sample-project failed: target directory is not empty"):
        main(["bootstrap", "sample-project", str(target_dir)])


def test_bootstrap_sample_project_fails_for_unknown_sample_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target_dir = tmp_path / "evaluation-repo"

    with pytest.raises(SystemExit) as exc_info:
        main(["bootstrap", "sample-project", str(target_dir), "--sample-project", "unknown-project"])

    assert exc_info.value.code == 2
    assert "invalid choice: 'unknown-project'" in capsys.readouterr().err
