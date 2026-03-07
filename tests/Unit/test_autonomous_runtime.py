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


def test_run_turnkey_project_reuses_single_ticket_runtime_and_persists_checkpoint(
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

    captured_calls: list[dict[str, object]] = []
    outcomes = [
        _project_outcome(ticket_id="T-000201", decision="accepted"),
        _project_outcome(ticket_id="T-000202", decision="accepted"),
        runtime.RuntimeConfigError(f"no ready tickets found in {tickets_dir}"),
    ]

    def fake_run_autonomous_ticket(**kwargs):
        captured_calls.append(kwargs)
        next_outcome = outcomes.pop(0)
        if isinstance(next_outcome, Exception):
            raise next_outcome
        return next_outcome

    monkeypatch.setattr(runtime, "run_autonomous_ticket", fake_run_autonomous_ticket)

    result = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=requirements_path,
        tickets_dir=tickets_dir,
        guardrails_path=guardrails_path,
        write_policy_path=write_policy_path,
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=mt_cli_path,
    )

    assert len(captured_calls) == 3
    assert captured_calls[0]["validation_commands"] == ("uv run pytest tests",)
    assert result.status == "succeeded"
    assert result.terminal_condition == "no_ready_ticket"
    assert result.completed_tickets == ("T-000201", "T-000202")
    assert result.retry_count == 0
    assert result.commit_policy == "disabled"
    checkpoint = json.loads(result.checkpoint_path.read_text())
    assert checkpoint["completed_tickets"] == ["T-000201", "T-000202"]
    summary = json.loads(result.summary_path.read_text())
    assert summary["terminal_condition"] == "no_ready_ticket"
    bundle = json.loads(result.review_bundle_path.read_text())
    assert bundle["completed_tickets"] == ["T-000201", "T-000202"]


def test_run_turnkey_project_resume_appends_to_existing_checkpoint(
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

    project_run_id = "project-run-resume"
    checkpoint_path = repo_root / ".higgs" / "local" / "project-runs" / project_run_id / "checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_run_id": project_run_id,
                "started_at": "2026-03-07T00:00:00Z",
                "updated_at": "2026-03-07T00:00:00Z",
                "status": "running",
                "terminal_condition": None,
                "resumed": False,
                "attempted_tickets": [
                    {
                        "ticket_id": "T-000201",
                        "execution_status": "succeeded",
                        "validation_decision": "accepted",
                        "validation_reason": None,
                        "telemetry_paths": {"events": ".higgs/local/runs/run-1/attempt-1/events.ndjson"},
                    }
                ],
                "completed_tickets": ["T-000201"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    outcomes = [
        _project_outcome(ticket_id="T-000202", decision="accepted"),
        runtime.RuntimeConfigError(f"no ready tickets found in {tickets_dir}"),
    ]

    def fake_run_autonomous_ticket(**kwargs):
        next_outcome = outcomes.pop(0)
        if isinstance(next_outcome, Exception):
            raise next_outcome
        return next_outcome

    monkeypatch.setattr(runtime, "run_autonomous_ticket", fake_run_autonomous_ticket)

    result = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=requirements_path,
        tickets_dir=tickets_dir,
        guardrails_path=guardrails_path,
        write_policy_path=write_policy_path,
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=mt_cli_path,
        project_run_id=project_run_id,
        resume=True,
    )

    assert result.resumed is True
    assert result.completed_tickets == ("T-000201", "T-000202")
    checkpoint = json.loads(result.checkpoint_path.read_text())
    assert checkpoint["resumed"] is True
    assert checkpoint["completed_tickets"] == ["T-000201", "T-000202"]


def test_run_turnkey_project_stops_on_max_ticket_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    outcomes = [_project_outcome(ticket_id="T-000201", decision="accepted")]

    def fake_run_autonomous_ticket(**kwargs):
        return outcomes.pop(0)

    monkeypatch.setattr(runtime, "run_autonomous_ticket", fake_run_autonomous_ticket)

    result = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=requirements_path,
        tickets_dir=tickets_dir,
        guardrails_path=guardrails_path,
        write_policy_path=write_policy_path,
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=mt_cli_path,
        max_tickets=1,
    )

    assert result.status == "stopped"
    assert result.terminal_condition == "max_ticket_limit_reached"


def test_run_turnkey_project_stops_after_repeated_runtime_failures(
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

    def fake_run_autonomous_ticket(**kwargs):
        raise runtime.RuntimeConfigError("provider transport failed")

    monkeypatch.setattr(runtime, "run_autonomous_ticket", fake_run_autonomous_ticket)

    result = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=requirements_path,
        tickets_dir=tickets_dir,
        guardrails_path=guardrails_path,
        write_policy_path=write_policy_path,
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=mt_cli_path,
        max_consecutive_failures=2,
    )

    assert result.status == "blocked"
    assert result.terminal_condition == "repeated_failures_exceeded"
    assert result.retry_count == 2
    bundle = json.loads(result.review_bundle_path.read_text())
    assert bundle["commit_policy"] == "disabled"


def test_run_turnkey_project_detects_blocked_dependency_graph(
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
    (tickets_dir / "T-000300.md").write_text(
        "---\n"
        "id: T-000300\n"
        "title: Blocked task\n"
        "status: ready\n"
        "priority: p1\n"
        "type: code\n"
        "effort: s\n"
        "higgs_schema_version: 1\n"
        "higgs_platform: agnostic\n"
        "higgs_execution_target: hosted\n"
        "higgs_tool_profile: none\n"
        "depends_on: [T-999999]\n"
        "---\n\n"
        "Blocked by missing dependency.\n"
    )

    def fake_run_autonomous_ticket(**kwargs):
        raise runtime.RuntimeConfigError(f"no ready tickets found in {tickets_dir}")

    monkeypatch.setattr(runtime, "run_autonomous_ticket", fake_run_autonomous_ticket)

    result = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=requirements_path,
        tickets_dir=tickets_dir,
        guardrails_path=guardrails_path,
        write_policy_path=write_policy_path,
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=mt_cli_path,
    )

    assert result.status == "blocked"
    assert result.terminal_condition == "blocked_dependency_graph"


def test_run_turnkey_project_rejects_unsupported_local_commit_request(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requirements_path = repo_root / "requirements.md"
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    guardrails_path = tmp_path / "guardrails.json"
    write_policy_path = tmp_path / "write-policy.json"

    requirements_path.write_text("Build the sample app.\n")
    guardrails_path.write_text(Path("config/guardrails.example.json").read_text())
    write_policy_path.write_text(Path("config/write-policy.example.json").read_text())

    with pytest.raises(runtime.RuntimeConfigError, match="local commit creation is not yet supported"):
        runtime.run_turnkey_project(
            repo_root=repo_root,
            requirements_path=requirements_path,
            tickets_dir=tickets_dir,
            guardrails_path=guardrails_path,
            write_policy_path=write_policy_path,
            validation_commands=("uv run pytest tests",),
            openrouter_api_key="test-key",
            create_local_commit=True,
        )


def _project_outcome(*, ticket_id: str, decision: str):
    return type(
        "FakeOutcome",
        (),
        {
            "ticket": type("Ticket", (), {"id": ticket_id})(),
            "execution_result": type(
                "ExecutionResult",
                (),
                {
                    "status": "succeeded" if decision != "rejected" else "failed",
                    "metadata": {
                        "telemetry_paths": {
                            "events": f".higgs/local/runs/{ticket_id}/attempt-1/events.ndjson",
                            "artifacts_dir": f".higgs/local/runs/{ticket_id}/attempt-1/artifacts",
                            "attempt_summaries": ".higgs/local/analytics/attempt-summaries.ndjson",
                        }
                    },
                },
            )(),
            "validation_decision": type(
                "ValidationDecision",
                (),
                {"decision": decision, "reason": None},
            )(),
        },
    )()