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


def _prepare_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "tickets").mkdir()
    (repo_root / "requirements.md").write_text("Build the sample app.\n")
    (repo_root / "tickets" / "T-920001.md").write_text(load_text_fixture("tickets/autonomous_ready_code.md"))
    (tmp_path / "guardrails.json").write_text(Path("config/guardrails.example.json").read_text())
    (tmp_path / "write-policy.json").write_text(Path("config/write-policy.example.json").read_text())
    (tmp_path / "mt.py").write_text("print('ok')\n")
    return repo_root


def _capture_mt_calls(calls: list[list[str]]):
    def fake_mt(mt_cli_path_arg: Path, args, *, cwd: Path) -> str:
        calls.append(list(args))
        return "ok"

    return fake_mt


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