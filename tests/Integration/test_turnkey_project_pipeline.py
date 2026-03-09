from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

import higgs_agent.runtime as runtime
from higgs_agent.analytics import (
    AnalyticsFilter,
    aggregate_attempt_summaries,
    build_ticket_metadata_index,
    load_attempt_summaries,
)
from higgs_agent.testing import load_json_fixture, load_text_fixture


class SequenceTransport:
    def __init__(self, responses: list[dict[str, object] | Exception]) -> None:
        self._responses = responses

    def complete(self, payload: dict[str, object], timeout_ms: int) -> dict[str, object]:
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_turnkey_project_pipeline_completes_fixture_project_and_remains_analytics_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _prepare_turnkey_repo(
        tmp_path, ["tickets/turnkey_ready_alpha.md", "tickets/turnkey_ready_beta.md"]
    )
    assumptions = load_json_fixture("config/turnkey_project_benchmark_assumptions.json")
    responses = [
        load_json_fixture("provider/openrouter_turnkey_alpha_success.json"),
        load_json_fixture("provider/openrouter_turnkey_beta_success.json"),
    ]

    monkeypatch.setattr(runtime, "OpenRouterHTTPTransport", _transport_factory(responses))
    monkeypatch.setattr(runtime, "_run_muontickets_command", _mutating_muontickets(repo_root))
    monkeypatch.setattr(runtime.subprocess, "run", _success_subprocess_runner())

    outcome = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
    )

    assert outcome.status == "succeeded"
    assert outcome.terminal_condition == "no_ready_ticket"
    assert outcome.completed_tickets == tuple(assumptions["expected_completed_tickets"])
    assert len(outcome.attempted_tickets) == assumptions["expected_attempts"]
    assert (repo_root / "src" / "app_alpha.py").is_file()
    assert (repo_root / "src" / "app_beta.py").is_file()

    for attempt in outcome.attempted_tickets:
        events_path = repo_root / attempt.telemetry_paths["events"]
        assert events_path.is_file()
        _validate_event_stream([json.loads(line) for line in events_path.read_text().splitlines()])

    attempt_summaries_path = (
        repo_root / ".higgs" / "local" / "analytics" / "attempt-summaries.ndjson"
    )
    summaries = load_attempt_summaries(attempt_summaries_path)
    assert len(summaries) == assumptions["expected_attempts"]
    for summary in summaries:
        _validate_attempt_summary(summary)

    analytics_report = aggregate_attempt_summaries(
        summaries,
        build_ticket_metadata_index(repo_root / "tickets"),
        AnalyticsFilter(group_by=tuple(assumptions["expected_group_by"])),
    )

    assert len(analytics_report.records) == 1
    assert (
        analytics_report.records[0]["metrics"]["attempts_total"] == assumptions["expected_attempts"]
    )
    _validate_analytics_aggregate(analytics_report.records[0])

    review_bundle = json.loads(outcome.review_bundle_path.read_text())
    assert review_bundle["commit_policy"] == assumptions["commit_policy"]
    assert review_bundle["completed_tickets"] == assumptions["expected_completed_tickets"]
    assert review_bundle["blocked_tickets"] == []
    assert review_bundle["untouched_tickets"] == []


def test_turnkey_project_pipeline_reports_blocked_dependency_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _prepare_turnkey_repo(tmp_path, ["tickets/turnkey_blocked_graph.md"])

    monkeypatch.setattr(runtime, "OpenRouterHTTPTransport", _transport_factory([]))

    outcome = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
    )

    assert outcome.status == "blocked"
    assert outcome.terminal_condition == "blocked_dependency_graph"
    assert outcome.attempted_tickets == ()
    review_bundle = json.loads(outcome.review_bundle_path.read_text())
    assert review_bundle["blocked_tickets"][0]["ticket_id"] == "T-930003"
    assert review_bundle["blocked_tickets"][0]["reason"].startswith("missing_dependency")


def test_turnkey_project_pipeline_stops_on_validation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _prepare_turnkey_repo(tmp_path, ["tickets/turnkey_ready_alpha.md"])
    responses = [load_json_fixture("provider/openrouter_turnkey_alpha_success.json")]

    monkeypatch.setattr(runtime, "OpenRouterHTTPTransport", _transport_factory(responses))
    monkeypatch.setattr(runtime, "_run_muontickets_command", _mutating_muontickets(repo_root))
    monkeypatch.setattr(runtime.subprocess, "run", _failing_validation_subprocess_runner())

    outcome = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
    )

    assert outcome.status == "blocked"
    assert outcome.terminal_condition == "validation_failure"
    assert outcome.completed_tickets == ()
    review_bundle = json.loads(outcome.review_bundle_path.read_text())
    assert review_bundle["blocked_tickets"][0]["ticket_id"] == "T-930001"
    assert review_bundle["blocked_tickets"][0]["reason"] == "validation_failed"


def test_turnkey_project_pipeline_resumes_after_ticket_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _prepare_turnkey_repo(
        tmp_path, ["tickets/turnkey_ready_alpha.md", "tickets/turnkey_ready_beta.md"]
    )
    responses = [
        load_json_fixture("provider/openrouter_turnkey_alpha_success.json"),
        load_json_fixture("provider/openrouter_turnkey_beta_success.json"),
    ]

    monkeypatch.setattr(runtime, "OpenRouterHTTPTransport", _transport_factory(responses))
    monkeypatch.setattr(runtime, "_run_muontickets_command", _mutating_muontickets(repo_root))
    monkeypatch.setattr(runtime.subprocess, "run", _success_subprocess_runner())

    first_outcome = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        project_run_id="project-run-resume-fixture",
        max_tickets=1,
    )

    assert first_outcome.status == "stopped"
    assert first_outcome.terminal_condition == "max_ticket_limit_reached"
    assert first_outcome.completed_tickets == ("T-930001",)

    resumed_outcome = runtime.run_turnkey_project(
        repo_root=repo_root,
        requirements_path=repo_root / "requirements.md",
        tickets_dir=repo_root / "tickets",
        guardrails_path=tmp_path / "guardrails.json",
        write_policy_path=tmp_path / "write-policy.json",
        validation_commands=("uv run pytest tests",),
        openrouter_api_key="test-key",
        muontickets_cli_path=tmp_path / "mt.py",
        project_run_id="project-run-resume-fixture",
        resume=True,
    )

    assert resumed_outcome.resumed is True
    assert resumed_outcome.status == "succeeded"
    assert resumed_outcome.completed_tickets == ("T-930001", "T-930002")
    checkpoint = json.loads(resumed_outcome.checkpoint_path.read_text())
    assert checkpoint["completed_tickets"] == ["T-930001", "T-930002"]


def _prepare_turnkey_repo(tmp_path: Path, ticket_fixtures: list[str]) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    tickets_dir = repo_root / "tickets"
    tickets_dir.mkdir()
    (repo_root / "requirements.md").write_text("Build the turnkey fixture app.\n")
    (tmp_path / "guardrails.json").write_text(Path("config/guardrails.example.json").read_text())
    (tmp_path / "write-policy.json").write_text(
        Path("config/write-policy.example.json").read_text()
    )
    (tmp_path / "mt.py").write_text("print('ok')\n")
    for fixture in ticket_fixtures:
        frontmatter = load_text_fixture(fixture)
        ticket_id = frontmatter.split("\n", 3)[1].split(": ", 1)[1]
        (tickets_dir / f"{ticket_id}.md").write_text(frontmatter)
    return repo_root


def _transport_factory(responses: list[dict[str, object] | Exception]):
    class FakeTransport:
        def __init__(self, api_key: str, base_url: str = "https://example.invalid") -> None:
            self._transport = SequenceTransport(responses)

        def complete(self, payload: dict[str, object], timeout_ms: int) -> dict[str, object]:
            return self._transport.complete(payload, timeout_ms)

    return FakeTransport


def _mutating_muontickets(repo_root: Path):
    def fake_mt(mt_cli_path_arg: Path, args, *, cwd: Path) -> str:
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
            return runtime.subprocess.CompletedProcess(command, 0, stdout="2 passed\n", stderr="")
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
    registry = (
        Registry()
        .with_resource(
            common_defs["$id"],
            Resource.from_contents(common_defs),
        )
        .with_resource(
            "common-defs.schema.json",
            Resource.from_contents(common_defs),
        )
    )
    validator = jsonschema.Draft202012Validator(event_schema, registry=registry)
    for event in events:
        validator.validate(event)


def _validate_attempt_summary(summary: dict[str, object]) -> None:
    summary_schema = json.loads(Path("schemas/execution-attempt.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = (
        Registry()
        .with_resource(
            common_defs["$id"],
            Resource.from_contents(common_defs),
        )
        .with_resource(
            "common-defs.schema.json",
            Resource.from_contents(common_defs),
        )
    )
    jsonschema.Draft202012Validator(summary_schema, registry=registry).validate(summary)


def _validate_analytics_aggregate(payload: dict[str, object]) -> None:
    aggregate_schema = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = (
        Registry()
        .with_resource(
            common_defs["$id"],
            Resource.from_contents(common_defs),
        )
        .with_resource(
            "common-defs.schema.json",
            Resource.from_contents(common_defs),
        )
    )
    jsonschema.Draft202012Validator(aggregate_schema, registry=registry).validate(payload)
