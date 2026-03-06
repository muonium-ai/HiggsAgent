from __future__ import annotations

from pathlib import Path

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


def _write_ticket_fixture(tmp_path: Path, relative_fixture_path: str) -> Path:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    ticket_content = load_text_fixture(relative_fixture_path)
    ticket_id = ticket_content.split("\nid: ", 1)[1].split("\n", 1)[0]
    (tickets_dir / f"{ticket_id}.md").write_text(ticket_content)
    return tickets_dir