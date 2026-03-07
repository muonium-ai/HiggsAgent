from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from higgs_agent.runtime import parse_changed_file_spec
import higgs_agent.cli as cli


def test_parse_changed_file_spec_parses_text_and_binary_variants() -> None:
    text_change = parse_changed_file_spec("src/app.py:12:3")
    binary_change = parse_changed_file_spec("assets/logo.png:0:0:binary")

    assert text_change.path == "src/app.py"
    assert text_change.additions == 12
    assert text_change.deletions == 3
    assert text_change.is_binary is False
    assert binary_change.is_binary is True


def test_run_ticketed_project_cli_invokes_runtime_and_prints_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requirements_path = repo_root / "requirements.md"
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    guardrails_path = repo_root / "guardrails.json"
    write_policy_path = repo_root / "write-policy.json"
    requirements_path.write_text("requirements\n")
    guardrails_path.write_text("{}\n")
    write_policy_path.write_text("{}\n")

    captured: dict[str, object] = {}

    def fake_run_ticketed_project(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            ticket=SimpleNamespace(id="T-900001"),
            route=SimpleNamespace(provider="openrouter", model_id="openai/gpt-4.1"),
            execution_result=SimpleNamespace(status="succeeded", output_text="Generated patch summary."),
            validation_decision=SimpleNamespace(decision="accepted"),
        )

    monkeypatch.setattr(cli, "run_ticketed_project", fake_run_ticketed_project)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    cli.main(
        [
            "run",
            "ticketed-project",
            "--repo-root",
            str(repo_root),
            "--requirements",
            str(requirements_path),
            "--tickets-dir",
            str(tickets_dir),
            "--guardrails",
            str(guardrails_path),
            "--write-policy",
            str(write_policy_path),
            "--changed-file",
            "src/app.py:12:3",
            "--validation-summary",
            "pytest passed",
        ]
    )

    assert captured["repo_root"] == repo_root
    assert captured["requirements_path"] == requirements_path
    assert captured["tickets_dir"] == tickets_dir
    assert captured["validation_summary"] == "pytest passed"
    assert captured["changed_files"][0].path == "src/app.py"
    output = capsys.readouterr().out
    assert "ticket: T-900001" in output
    assert "validation_decision: accepted" in output


def test_run_ticketed_project_cli_requires_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requirements_path = repo_root / "requirements.md"
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    guardrails_path = repo_root / "guardrails.json"
    write_policy_path = repo_root / "write-policy.json"
    requirements_path.write_text("requirements\n")
    guardrails_path.write_text("{}\n")
    write_policy_path.write_text("{}\n")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="OpenRouter API key required"):
        cli.main(
            [
                "run",
                "ticketed-project",
                "--repo-root",
                str(repo_root),
                "--requirements",
                str(requirements_path),
                "--tickets-dir",
                str(tickets_dir),
                "--guardrails",
                str(guardrails_path),
                "--write-policy",
                str(write_policy_path),
                "--changed-file",
                "src/app.py:12:3",
                "--validation-summary",
                "pytest passed",
            ]
        )
