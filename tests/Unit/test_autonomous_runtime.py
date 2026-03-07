from __future__ import annotations

import json
from pathlib import Path

import pytest

import higgs_agent.runtime as runtime


class FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response

    def complete(self, payload: dict[str, object], timeout_ms: int) -> dict[str, object]:
        return self.response


def test_run_autonomous_ticket_materializes_files_and_updates_ticket_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requirements_path = repo_root / "requirements.md"
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    guardrails_path = tmp_path / "guardrails.json"
    write_policy_path = tmp_path / "write-policy.json"
    mt_cli_path = tmp_path / "mt.py"

    requirements_path.write_text("Build the sample app.\n")
    guardrails_path.write_text(Path("config/guardrails.example.json").read_text())
    write_policy_path.write_text(Path("config/write-policy.example.json").read_text())
    mt_cli_path.write_text("print('ok')\n")
    (tickets_dir / "T-000100.md").write_text(
        "---\n"
        "id: T-000100\n"
        "title: Add scaffold\n"
        "status: ready\n"
        "priority: p1\n"
        "type: code\n"
        "effort: s\n"
        "higgs_schema_version: 1\n"
        "higgs_platform: agnostic\n"
        "higgs_execution_target: hosted\n"
        "higgs_tool_profile: none\n"
        "depends_on: []\n"
        "---\n\n"
        "Create the initial scaffold.\n"
    )

    mt_calls: list[list[str]] = []

    def fake_mt(mt_cli_path_arg: Path, args, *, cwd: Path) -> str:
        mt_calls.append(list(args))
        return "ok"

    def fake_subprocess_run(command, **kwargs):
        if command == ["git", "rev-parse", "HEAD"]:
            return runtime.subprocess.CompletedProcess(
                command,
                0,
                stdout="deadbeef\n",
                stderr="",
            )
        if command == "uv run pytest tests":
            return runtime.subprocess.CompletedProcess(
                command,
                0,
                stdout="1 passed\n",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(runtime, "_run_muontickets_command", fake_mt)
    monkeypatch.setattr(runtime.subprocess, "run", fake_subprocess_run)

    outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=requirements_path,
        tickets_dir=tickets_dir,
        guardrails_path=guardrails_path,
        write_policy_path=write_policy_path,
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=mt_cli_path,
        transport=FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Created initial scaffold",
                                    "directories": ["src/game_of_life", "tests"],
                                    "writes": [
                                        {
                                            "path": "src/game_of_life/__init__.py",
                                            "content": '"""Game of Life."""\n',
                                        },
                                        {
                                            "path": "tests/test_scaffold.py",
                                            "content": "def test_placeholder():\n    assert True\n",
                                        },
                                    ],
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }
        ),
    )

    assert outcome.execution_result.status == "succeeded"
    assert outcome.validation_decision.decision == "accepted"
    assert (repo_root / "src" / "game_of_life" / "__init__.py").is_file()
    assert (repo_root / "tests" / "test_scaffold.py").is_file()
    assert mt_calls[0][:2] == ["claim", "T-000100"]
    assert any(call[0] == "comment" for call in mt_calls)
    assert any(call[:3] == ["set-status", "T-000100", "needs_review"] for call in mt_calls)
    assert outcome.execution_result.metadata["telemetry_paths"]["events"].endswith("events.ndjson")


def test_run_autonomous_ticket_rejects_invalid_model_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requirements_path = repo_root / "requirements.md"
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    guardrails_path = tmp_path / "guardrails.json"
    write_policy_path = tmp_path / "write-policy.json"
    mt_cli_path = tmp_path / "mt.py"

    requirements_path.write_text("Build the sample app.\n")
    guardrails_path.write_text(Path("config/guardrails.example.json").read_text())
    write_policy_path.write_text(Path("config/write-policy.example.json").read_text())
    mt_cli_path.write_text("print('ok')\n")
    (tickets_dir / "T-000101.md").write_text(
        "---\n"
        "id: T-000101\n"
        "title: Add scaffold\n"
        "status: ready\n"
        "priority: p1\n"
        "type: code\n"
        "effort: s\n"
        "higgs_schema_version: 1\n"
        "higgs_platform: agnostic\n"
        "higgs_execution_target: hosted\n"
        "higgs_tool_profile: none\n"
        "depends_on: []\n"
        "---\n\n"
        "Create the initial scaffold.\n"
    )

    mt_calls: list[list[str]] = []

    def fake_mt(mt_cli_path_arg: Path, args, *, cwd: Path) -> str:
        mt_calls.append(list(args))
        return "ok"

    monkeypatch.setattr(runtime, "_run_muontickets_command", fake_mt)

    outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=requirements_path,
        tickets_dir=tickets_dir,
        guardrails_path=guardrails_path,
        write_policy_path=write_policy_path,
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=mt_cli_path,
        transport=FakeTransport(
            {
                "choices": [{"message": {"content": "not json"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }
        ),
    )

    assert outcome.execution_result.status == "failed"
    assert outcome.validation_decision.decision == "rejected"
    assert any(call[0] == "comment" for call in mt_calls)