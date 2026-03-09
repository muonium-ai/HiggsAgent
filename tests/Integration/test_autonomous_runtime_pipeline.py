from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

import higgs_agent.runtime as runtime
from higgs_agent.testing import load_json_fixture, load_text_fixture


class FakeTransport:
    def __init__(self, responses: list[dict[str, object] | Exception]) -> None:
        self._responses = responses

    def complete(self, payload: dict[str, object], timeout_ms: int) -> dict[str, object]:
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_autonomous_runtime_persists_schema_valid_successful_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _prepare_repo(tmp_path)
    mt_calls: list[list[str]] = []

    monkeypatch.setattr(runtime, "_run_muontickets_command", _capture_mt_calls(mt_calls))
    monkeypatch.setattr(runtime.subprocess, "run", _success_subprocess_runner())

    outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        transport=FakeTransport([load_json_fixture("provider/openrouter_autonomous_scaffold_success.json")]),
    )

    assert outcome.execution_result.status == "succeeded"
    assert outcome.validation_decision.decision == "accepted"
    assert any(call[:3] == ["set-status", "T-920001", "needs_review"] for call in mt_calls)

    telemetry_paths = outcome.execution_result.metadata["telemetry_paths"]
    events_path = repo_root / telemetry_paths["events"]
    attempt_summaries_path = repo_root / telemetry_paths["attempt_summaries"]
    assert events_path.is_file()
    assert attempt_summaries_path.is_file()

    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert "prompt.rendered" in [event["event_type"] for event in events]
    assert "file.written" in [event["event_type"] for event in events]
    _validate_event_stream(events)

    summaries = [json.loads(line) for line in attempt_summaries_path.read_text().splitlines()]
    assert summaries[0]["final_result"] == "succeeded"
    _validate_attempt_summary(summaries[0])


def test_autonomous_runtime_records_provider_failure_without_advancing_ticket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _prepare_repo(tmp_path)
    mt_calls: list[list[str]] = []

    monkeypatch.setattr(runtime, "_run_muontickets_command", _capture_mt_calls(mt_calls))
    monkeypatch.setattr(runtime.subprocess, "run", _success_subprocess_runner())

    outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        transport=FakeTransport([TimeoutError("provider timed out")]),
    )

    assert outcome.execution_result.status == "failed"
    assert outcome.validation_decision.decision == "rejected"
    assert not any(call[:3] == ["set-status", "T-920001", "needs_review"] for call in mt_calls)
    assert any(call[0] == "comment" for call in mt_calls)


def test_autonomous_runtime_rejects_failed_validation_without_advancing_ticket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _prepare_repo(tmp_path)
    mt_calls: list[list[str]] = []

    monkeypatch.setattr(runtime, "_run_muontickets_command", _capture_mt_calls(mt_calls))
    monkeypatch.setattr(runtime.subprocess, "run", _failing_validation_subprocess_runner())

    outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        transport=FakeTransport([load_json_fixture("provider/openrouter_autonomous_scaffold_success.json")]),
    )

    assert outcome.validation_decision.decision == "rejected"
    assert outcome.validation_decision.reason == "validation_failed"
    assert not any(call[:3] == ["set-status", "T-920001", "needs_review"] for call in mt_calls)


def test_autonomous_runtime_writes_review_handoff_for_protected_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _prepare_repo(tmp_path)
    mt_calls: list[list[str]] = []

    monkeypatch.setattr(runtime, "_run_muontickets_command", _capture_mt_calls(mt_calls))
    monkeypatch.setattr(runtime.subprocess, "run", _success_subprocess_runner())

    outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        transport=FakeTransport([load_json_fixture("provider/openrouter_autonomous_protected_write.json")]),
    )

    assert outcome.validation_decision.decision == "handoff_required"
    assert outcome.validation_decision.reason == "protected_path_touched"
    assert any(call[:3] == ["set-status", "T-920001", "needs_review"] for call in mt_calls)

    telemetry_paths = outcome.execution_result.metadata["telemetry_paths"]
    artifacts_dir = repo_root / telemetry_paths["artifacts_dir"]
    assert (artifacts_dir / "review-handoff.txt").is_file()


def test_autonomous_runtime_materializes_fixture_scaffold_then_applies_follow_up_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _prepare_repo(
        tmp_path,
        [
            "tickets/autonomous_ready_code.md",
            "tickets/autonomous_ready_patch.md",
        ],
    )
    mt_calls: list[list[str]] = []
    _add_allowed_write_path(tmp_path / "write-policy.json", "fixtures/**")

    monkeypatch.setattr(runtime, "_run_muontickets_command", _mutating_muontickets(repo_root, mt_calls))
    monkeypatch.setattr(runtime.subprocess, "run", _success_subprocess_runner())

    scaffold_outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        transport=FakeTransport([load_json_fixture("provider/openrouter_autonomous_game_of_life_scaffold.json")]),
    )

    assert scaffold_outcome.execution_result.status == "succeeded"
    assert scaffold_outcome.validation_decision.decision == "accepted"
    assert scaffold_outcome.validation_decision.changed_paths == (
        "src/game_of_life/__init__.py",
        "src/game_of_life/engine.py",
        "tests/test_engine.py",
        "fixtures/blinker.txt",
    )
    assert (repo_root / "src" / "game_of_life" / "engine.py").is_file()
    assert (repo_root / "fixtures" / "blinker.txt").read_text() == ".#.\n.#.\n.#.\n"
    scaffold_artifacts_dir = repo_root / scaffold_outcome.execution_result.metadata["telemetry_paths"]["artifacts_dir"]
    scaffold_plan = json.loads((scaffold_artifacts_dir / "materialization-plan.json").read_text())
    assert scaffold_plan["writes"] == [
        "src/game_of_life/__init__.py",
        "src/game_of_life/engine.py",
        "tests/test_engine.py",
        "fixtures/blinker.txt",
    ]
    scaffold_events = [json.loads(line) for line in (repo_root / scaffold_outcome.execution_result.metadata["telemetry_paths"]["events"]).read_text().splitlines()]
    assert "directory.created" in [event["event_type"] for event in scaffold_events]
    assert "file.written" in [event["event_type"] for event in scaffold_events]
    _validate_event_stream(scaffold_events)

    patch_outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        transport=FakeTransport([load_json_fixture("provider/openrouter_autonomous_game_of_life_patch.json")]),
    )

    assert patch_outcome.ticket.id == "T-920002"
    assert patch_outcome.execution_result.status == "succeeded"
    assert patch_outcome.validation_decision.decision == "accepted"
    assert patch_outcome.validation_decision.changed_paths == (
        "src/game_of_life/engine.py",
        "tests/test_engine.py",
    )
    assert "return [\"...\", \"###\", \"...\"]" in (repo_root / "src" / "game_of_life" / "engine.py").read_text()
    assert "test_next_state_rotates_blinker" in (repo_root / "tests" / "test_engine.py").read_text()
    patch_artifacts_dir = repo_root / patch_outcome.execution_result.metadata["telemetry_paths"]["artifacts_dir"]
    patch_plan = json.loads((patch_artifacts_dir / "materialization-plan.json").read_text())
    assert patch_plan["patches"] == [
        {
            "path": "src/game_of_life/engine.py",
            "before": "    return board\n",
            "after": "    if board == [\".#.\", \".#.\", \".#.\"]:\n        return [\"...\", \"###\", \"...\"]\n    return board\n",
        },
        {
            "path": "tests/test_engine.py",
            "before": "def test_next_state_preserves_board():\n    assert next_state([\".#.\"]) == [\".#.\"]\n",
            "after": "def test_next_state_preserves_board():\n    assert next_state([\".#.\"]) == [\".#.\"]\n\n\ndef test_next_state_rotates_blinker():\n    assert next_state([\".#.\", \".#.\", \".#.\"]) == [\"...\", \"###\", \"...\"]\n",
        },
    ]
    patch_events = [json.loads(line) for line in (repo_root / patch_outcome.execution_result.metadata["telemetry_paths"]["events"]).read_text().splitlines()]
    assert "file.patched" in [event["event_type"] for event in patch_events]
    _validate_event_stream(patch_events)

    attempt_summaries_path = repo_root / ".higgs" / "local" / "analytics" / "attempt-summaries.ndjson"
    summaries = [json.loads(line) for line in attempt_summaries_path.read_text().splitlines()]
    assert len(summaries) == 2
    assert [summary["ticket_id"] for summary in summaries] == ["T-920001", "T-920002"]
    for summary in summaries:
        _validate_attempt_summary(summary)

    assert any(call[:3] == ["set-status", "T-920001", "needs_review"] for call in mt_calls)
    assert any(call[:3] == ["set-status", "T-920002", "needs_review"] for call in mt_calls)


def test_autonomous_runtime_rejects_fixture_patch_without_corrupting_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _prepare_repo(tmp_path, ["tickets/autonomous_ready_patch.md"])
    mt_calls: list[list[str]] = []
    (repo_root / "src" / "game_of_life").mkdir(parents=True)
    original_content = (
        "def next_state(board: list[str]) -> list[str]:\n"
        "    if board:\n"
        "        return board\n"
        "    return board\n"
    )
    (repo_root / "src" / "game_of_life" / "engine.py").write_text(original_content)

    monkeypatch.setattr(runtime, "_run_muontickets_command", _mutating_muontickets(repo_root, mt_calls))
    monkeypatch.setattr(runtime.subprocess, "run", _success_subprocess_runner())

    outcome = runtime.run_autonomous_ticket(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        transport=FakeTransport([load_json_fixture("provider/openrouter_autonomous_patch_ambiguous.json")]),
    )

    assert outcome.execution_result.status == "failed"
    assert outcome.validation_decision.decision == "rejected"
    assert outcome.validation_decision.reason == "materialization_failure"
    assert "could not be materialized" in outcome.validation_decision.diagnostics[0]
    assert (repo_root / "src" / "game_of_life" / "engine.py").read_text() == original_content
    assert not any(call[:3] == ["set-status", "T-920002", "needs_review"] for call in mt_calls)

    events_path = repo_root / outcome.execution_result.metadata["telemetry_paths"]["events"]
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    _validate_event_stream(events)
    summaries = [json.loads(line) for line in (repo_root / ".higgs" / "local" / "analytics" / "attempt-summaries.ndjson").read_text().splitlines()]
    assert len(summaries) == 1
    assert summaries[0]["final_result"] == "failed"
    _validate_attempt_summary(summaries[0])


def _prepare_repo(tmp_path: Path, ticket_fixtures: list[str] | None = None) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    (repo_root / "requirements.md").write_text("Build the sample app.\n")
    (tmp_path / "guardrails.json").write_text(Path("config/guardrails.example.json").read_text())
    (tmp_path / "write-policy.json").write_text(Path("config/write-policy.example.json").read_text())
    (tmp_path / "mt.py").write_text("print('ok')\n")
    selected_fixtures = ticket_fixtures or ["tickets/autonomous_ready_code.md"]
    for fixture in selected_fixtures:
        frontmatter = load_text_fixture(fixture)
        ticket_id = frontmatter.split("\n", 3)[1].split(": ", 1)[1]
        (tickets_dir / f"{ticket_id}.md").write_text(frontmatter)
    return repo_root


def _capture_mt_calls(calls: list[list[str]]):
    def fake_mt(mt_cli_path_arg: Path, args, *, cwd: Path) -> str:
        calls.append(list(args))
        return "ok"

    return fake_mt


def _mutating_muontickets(repo_root: Path, calls: list[list[str]]):
    def fake_mt(mt_cli_path_arg: Path, args, *, cwd: Path) -> str:
        calls.append(list(args))
        command = args[0]
        if command == "claim":
            _set_ticket_status(repo_root / "tickets" / f"{args[1]}.md", "claimed")
            return "claimed"
        if command == "set-status":
            _set_ticket_status(repo_root / "tickets" / f"{args[1]}.md", args[2])
            return "updated"
        if command == "comment":
            return "commented"
        raise AssertionError(f"unexpected mt command: {args}")

    return fake_mt


def _add_allowed_write_path(policy_path: Path, path_pattern: str) -> None:
    policy = json.loads(policy_path.read_text())
    allowed_paths = list(policy["allowed_paths"])
    if path_pattern not in allowed_paths:
        allowed_paths.append(path_pattern)
    policy["allowed_paths"] = allowed_paths
    policy_path.write_text(json.dumps(policy, indent=2) + "\n")


def _set_ticket_status(ticket_path: Path, status: str) -> None:
    lines = ticket_path.read_text().splitlines()
    for index, line in enumerate(lines):
        if line.startswith("status: "):
            lines[index] = f"status: {status}"
            ticket_path.write_text("\n".join(lines) + "\n")
            return
    raise AssertionError(f"missing status field in {ticket_path}")


def _success_subprocess_runner():
    def fake_run(command, **kwargs):
        if command == ["git", "rev-parse", "HEAD"]:
            return runtime.subprocess.CompletedProcess(command, 0, stdout="deadbeef\n", stderr="")
        if command == "uv run pytest tests":
            return runtime.subprocess.CompletedProcess(command, 0, stdout="1 passed\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    return fake_run


def _failing_validation_subprocess_runner():
    def fake_run(command, **kwargs):
        if command == ["git", "rev-parse", "HEAD"]:
            return runtime.subprocess.CompletedProcess(command, 0, stdout="deadbeef\n", stderr="")
        if command == "uv run pytest tests":
            return runtime.subprocess.CompletedProcess(command, 1, stdout="", stderr="1 failed\n")
        raise AssertionError(f"unexpected command: {command}")

    return fake_run


def _validate_event_stream(events: list[dict[str, object]]) -> None:
    event_schema = json.loads(Path("schemas/execution-event.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = Registry().with_resource(
        common_defs["$id"],
        Resource.from_contents(common_defs),
    ).with_resource(
        "common-defs.schema.json",
        Resource.from_contents(common_defs),
    )
    validator = jsonschema.Draft202012Validator(event_schema, registry=registry)
    for event in events:
        validator.validate(event)


def _validate_attempt_summary(summary: dict[str, object]) -> None:
    summary_schema = json.loads(Path("schemas/execution-attempt.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = Registry().with_resource(
        common_defs["$id"],
        Resource.from_contents(common_defs),
    ).with_resource(
        "common-defs.schema.json",
        Resource.from_contents(common_defs),
    )
    validator = jsonschema.Draft202012Validator(summary_schema, registry=registry)
    validator.validate(summary)