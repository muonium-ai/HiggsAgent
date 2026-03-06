from __future__ import annotations

from pathlib import Path

import json

import jsonschema
from referencing import Registry, Resource

from higgs_agent.application import dispatch_next_ready_ticket
from higgs_agent.testing import load_json_fixture, load_text_fixture
from higgs_agent.validation import ProposedFileChange


class FakeTransport:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = responses
        self.calls: list[tuple[dict[str, object], int]] = []

    def complete(self, payload: dict[str, object], timeout_ms: int) -> dict[str, object]:
        self.calls.append((payload, timeout_ms))
        return self._responses.pop(0)


class FakeLocalTransport:
    def __init__(self, responses: list[dict[str, object] | Exception]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str | None, int]] = []

    def generate(self, prompt: str, system_prompt: str | None, timeout_ms: int) -> dict[str, object]:
        self.calls.append((prompt, system_prompt, timeout_ms))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_dispatcher_pipeline_accepts_clean_allowed_changes(tmp_path: Path) -> None:
    tickets_dir = _write_ticket_fixture(tmp_path, "tickets/dispatcher_ready_docs.md")
    transport = FakeTransport([load_json_fixture("provider/openrouter_success_minimal.json")])

    outcome = dispatch_next_ready_ticket(
        tickets_dir,
        transport=transport,
        guardrails_path=Path("config/guardrails.example.json"),
        write_policy_path=Path("config/write-policy.example.json"),
        planned_changes=(
            ProposedFileChange(path="docs/operators/runbook.md", additions=12, deletions=2),
        ),
        validation_summary="dispatcher pipeline succeeded",
    )

    assert outcome is not None
    assert outcome.ticket.id == "T-910001"
    assert outcome.route.selected is True
    assert outcome.execution_result.status == "succeeded"
    assert outcome.validation_decision.decision == "accepted"
    assert transport.calls


def test_dispatcher_pipeline_requires_handoff_for_protected_paths(tmp_path: Path) -> None:
    tickets_dir = _write_ticket_fixture(tmp_path, "tickets/dispatcher_ready_code.md")
    transport = FakeTransport([load_json_fixture("provider/openrouter_success_minimal.json")])

    outcome = dispatch_next_ready_ticket(
        tickets_dir,
        transport=transport,
        guardrails_path=Path("config/guardrails.example.json"),
        write_policy_path=Path("config/write-policy.example.json"),
        planned_changes=(
            ProposedFileChange(path="pyproject.toml", additions=1, deletions=1),
        ),
        validation_summary="dispatcher pipeline succeeded but touched protected path",
    )

    assert outcome is not None
    assert outcome.execution_result.status == "succeeded"
    assert outcome.validation_decision.decision == "handoff_required"
    assert outcome.validation_decision.reason == "protected_path_touched"
    assert "Ticket ID: T-910002" in (outcome.validation_decision.handoff_message or "")


def test_dispatcher_pipeline_blocks_local_execution_before_transport(tmp_path: Path) -> None:
    tickets_dir = _write_ticket_fixture(tmp_path, "tickets/dispatcher_ready_local.md")
    transport = FakeTransport([])

    outcome = dispatch_next_ready_ticket(
        tickets_dir,
        transport=transport,
        guardrails_path=Path("config/guardrails.example.json"),
        write_policy_path=Path("config/write-policy.example.json"),
        planned_changes=(),
        validation_summary="route blocked before execution",
    )

    assert outcome is not None
    assert outcome.route.selected is False
    assert outcome.execution_result.status == "blocked"
    assert outcome.validation_decision.decision == "rejected"
    assert outcome.validation_decision.reason == "executor_did_not_succeed"
    assert transport.calls == []


def test_dispatcher_pipeline_executes_explicit_local_route_when_transport_is_available(tmp_path: Path) -> None:
    tickets_dir = _write_ticket_fixture(tmp_path, "tickets/dispatcher_ready_local.md")
    transport = FakeTransport([])
    local_transport = FakeLocalTransport(
        [
            {
                "output_text": "Local execution completed",
                "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            }
        ]
    )

    outcome = dispatch_next_ready_ticket(
        tickets_dir,
        transport=transport,
        local_transport=local_transport,
        guardrails_path=Path("config/guardrails.example.json"),
        write_policy_path=Path("config/write-policy.example.json"),
        planned_changes=(),
        validation_summary="local execution succeeded",
    )

    assert outcome is not None
    assert outcome.route.provider == "local"
    assert outcome.execution_result.status == "succeeded"
    assert outcome.execution_result.output_text == "Local execution completed"
    assert outcome.execution_result.metadata["fallback_triggered"] is False
    assert local_transport.calls
    assert transport.calls == []


def test_dispatcher_pipeline_falls_back_from_local_to_hosted_for_auto_route(tmp_path: Path) -> None:
    tickets_dir = _write_ticket_fixture(tmp_path, "tickets/dispatcher_ready_docs.md")
    transport = FakeTransport([load_json_fixture("provider/openrouter_success_minimal.json")])
    local_transport = FakeLocalTransport([TimeoutError("local runtime unavailable")])

    outcome = dispatch_next_ready_ticket(
        tickets_dir,
        transport=transport,
        local_transport=local_transport,
        guardrails_path=Path("config/guardrails.example.json"),
        write_policy_path=Path("config/write-policy.example.json"),
        planned_changes=(),
        validation_summary="local fallback to hosted succeeded",
    )

    assert outcome is not None
    assert outcome.route.provider == "local"
    assert outcome.execution_result.status == "succeeded"
    assert outcome.execution_result.output_text == "Generated patch summary."
    assert outcome.execution_result.retry_count == 1
    assert outcome.execution_result.metadata["fallback_triggered"] is True
    assert outcome.execution_result.metadata["fallback_route"]["provider"] == "openrouter"
    assert "retry.scheduled" in [event["event_type"] for event in outcome.execution_result.events]
    assert [event["sequence"] for event in outcome.execution_result.events] == list(
        range(len(outcome.execution_result.events))
    )
    _validate_event_stream(outcome.execution_result.events)
    _validate_attempt_summary(outcome.execution_result.attempt_summary)
    assert local_transport.calls
    assert transport.calls


def test_dispatcher_pipeline_keeps_explicit_local_failure_observable_without_hosted_fallback(
    tmp_path: Path,
) -> None:
    tickets_dir = _write_ticket_fixture(tmp_path, "tickets/dispatcher_ready_local.md")
    transport = FakeTransport([])
    local_transport = FakeLocalTransport([TimeoutError("local runtime unavailable")])

    outcome = dispatch_next_ready_ticket(
        tickets_dir,
        transport=transport,
        local_transport=local_transport,
        guardrails_path=Path("config/guardrails.example.json"),
        write_policy_path=Path("config/write-policy.example.json"),
        planned_changes=(),
        validation_summary="explicit local execution failed",
    )

    assert outcome is not None
    assert outcome.route.provider == "local"
    assert outcome.execution_result.status == "failed"
    assert outcome.execution_result.metadata["fallback_triggered"] is False
    assert outcome.execution_result.attempt_summary["error"]["kind"] == "timeout"
    _validate_event_stream(outcome.execution_result.events)
    _validate_attempt_summary(outcome.execution_result.attempt_summary)
    assert local_transport.calls
    assert transport.calls == []


def _write_ticket_fixture(tmp_path: Path, relative_fixture_path: str) -> Path:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    ticket_content = load_text_fixture(relative_fixture_path)
    ticket_id = ticket_content.split("\nid: ", 1)[1].split("\n", 1)[0]
    (tickets_dir / f"{ticket_id}.md").write_text(ticket_content)
    return tickets_dir


def _validate_event_stream(events: tuple[dict[str, object], ...]) -> None:
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