from __future__ import annotations

import subprocess
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


def test_run_autonomous_ticket_cli_invokes_runtime_and_prints_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requirements_path = repo_root / "requirements.md"
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    guardrails_path = repo_root / "guardrails.json"
    write_policy_path = repo_root / "write-policy.json"
    mt_cli_path = repo_root / "mt.py"
    requirements_path.write_text("requirements\n")
    guardrails_path.write_text("{}\n")
    write_policy_path.write_text("{}\n")
    mt_cli_path.write_text("print('ok')\n")

    captured: dict[str, object] = {}

    def fake_run_autonomous_ticket(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            ticket=SimpleNamespace(id="T-900002"),
            route=SimpleNamespace(provider="openrouter", model_id="openai/gpt-4.1"),
            execution_result=SimpleNamespace(
                status="succeeded",
                output_text='{"summary":"done"}',
                metadata={
                    "telemetry_paths": {
                        "events": ".higgs/local/runs/run-1/attempt-1/events.ndjson",
                        "artifacts_dir": ".higgs/local/runs/run-1/attempt-1/artifacts",
                        "attempt_summaries": ".higgs/local/analytics/attempt-summaries.ndjson",
                    }
                },
            ),
            validation_decision=SimpleNamespace(
                decision="accepted",
                changed_paths=("src/app.py", "tests/test_app.py"),
            ),
        )

    monkeypatch.setattr(cli, "run_autonomous_ticket", fake_run_autonomous_ticket)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    cli.main(
        [
            "run",
            "autonomous-ticket",
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
            "--validation-command",
            "uv run pytest tests",
            "--muontickets-cli",
            str(mt_cli_path),
        ]
    )

    assert captured["repo_root"] == repo_root
    assert captured["requirements_path"] == requirements_path
    assert captured["validation_commands"] == ("uv run pytest tests",)
    assert captured["muontickets_cli_path"] == mt_cli_path
    output = capsys.readouterr().out
    assert "ticket: T-900002" in output
    assert "changed_paths: src/app.py, tests/test_app.py" in output


def test_run_autonomous_ticket_cli_requires_api_key(
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
                "autonomous-ticket",
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
                "--validation-command",
                "uv run pytest tests",
            ]
        )


def test_run_turnkey_project_cli_invokes_runtime_and_prints_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requirements_path = repo_root / "requirements.md"
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    guardrails_path = repo_root / "guardrails.json"
    write_policy_path = repo_root / "write-policy.json"
    mt_cli_path = repo_root / "mt.py"
    requirements_path.write_text("requirements\n")
    guardrails_path.write_text("{}\n")
    write_policy_path.write_text("{}\n")
    mt_cli_path.write_text("print('ok')\n")

    captured: dict[str, object] = {}

    def fake_run_turnkey_project(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            project_run_id="project-run-123",
            status="succeeded",
            terminal_condition="no_ready_ticket",
            resumed=False,
            attempted_tickets=(SimpleNamespace(ticket_id="T-900010"), SimpleNamespace(ticket_id="T-900011")),
            completed_tickets=("T-900010", "T-900011"),
            checkpoint_path=repo_root / ".higgs" / "local" / "project-runs" / "project-run-123" / "checkpoint.json",
            summary_path=repo_root / ".higgs" / "local" / "project-runs" / "project-run-123" / "summary.json",
        )

    monkeypatch.setattr(cli, "run_turnkey_project", fake_run_turnkey_project)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    cli.main(
        [
            "run",
            "turnkey-project",
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
            "--validation-command",
            "uv run pytest tests",
            "--muontickets-cli",
            str(mt_cli_path),
            "--project-run-id",
            "project-run-123",
            "--resume",
        ]
    )

    assert captured["project_run_id"] == "project-run-123"
    assert captured["resume"] is True
    assert captured["validation_commands"] == ("uv run pytest tests",)
    output = capsys.readouterr().out
    assert "project_run_id: project-run-123" in output
    assert "terminal_condition: no_ready_ticket" in output


def test_run_turnkey_project_cli_requires_api_key(
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
                "turnkey-project",
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
                "--validation-command",
                "uv run pytest tests",
            ]
        )


def test_validate_tickets_cli_invokes_muontickets_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = tmp_path / "repo"
    mt_cli = repo_root / "tickets" / "mt" / "muontickets" / "muontickets"
    mt_cli.mkdir(parents=True)
    (mt_cli / "mt.py").write_text("print('ok')\n")

    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="board valid\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli.main(["validate", "tickets", "--repo-root", str(repo_root)])

    assert captured["command"][1].endswith("tickets/mt/muontickets/muontickets/mt.py")
    assert captured["command"][2] == "validate"
    assert captured["cwd"] == repo_root
    assert "board valid" in capsys.readouterr().out


def test_validate_tickets_cli_reports_missing_muontickets_cli(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(SystemExit, match=r"validate tickets failed: MuonTickets CLI not found"):
        cli.main(["validate", "tickets", "--repo-root", str(repo_root)])
