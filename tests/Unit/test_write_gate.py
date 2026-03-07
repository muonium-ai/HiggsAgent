from __future__ import annotations

from pathlib import Path

import pytest

from higgs_agent.providers.contract import ProviderUsage
from higgs_agent.validation import (
    ProposedFileChange,
    ValidationInput,
    evaluate_write_request,
    load_write_policy,
)


def test_write_gate_accepts_allowed_deterministic_changes() -> None:
    decision = evaluate_write_request(
        _validation_input(
            changed_files=(
                ProposedFileChange(
                    path="src/higgs_agent/routing/policy.py",
                    additions=20,
                    deletions=4,
                ),
                ProposedFileChange(
                    path="tests/Unit/test_routing_policy.py",
                    additions=10,
                    deletions=0,
                ),
            )
        ),
        load_write_policy(Path("config/write-policy.example.json")),
    )

    assert decision.decision == "accepted"
    assert decision.requires_human_review is False


def test_write_gate_requires_review_for_protected_paths() -> None:
    decision = evaluate_write_request(
        _validation_input(
            changed_files=(
                ProposedFileChange(path="pyproject.toml", additions=1, deletions=1),
            )
        ),
        load_write_policy(Path("config/write-policy.example.json")),
    )

    assert decision.decision == "handoff_required"
    assert decision.reason == "protected_path_touched"
    assert "Ticket ID: T-000015" in (decision.handoff_message or "")


def test_write_gate_requires_review_for_disallowed_paths() -> None:
    decision = evaluate_write_request(
        _validation_input(
            changed_files=(
                ProposedFileChange(path="var/runtime/cache.json", additions=10, deletions=0),
            )
        ),
        load_write_policy(Path("config/write-policy.example.json")),
    )

    assert decision.decision == "handoff_required"
    assert "disallowed_paths:var/runtime/cache.json" in decision.diagnostics


def test_write_gate_requires_review_for_secret_suspect() -> None:
    decision = evaluate_write_request(
        _validation_input(
            output_text="Authorization: Bearer super-secret-token",
            changed_files=(
                ProposedFileChange(
                    path="src/higgs_agent/validation/write_gate.py",
                    additions=5,
                    deletions=0,
                ),
            ),
        ),
        load_write_policy(Path("config/write-policy.example.json")),
    )

    assert decision.decision == "handoff_required"
    assert decision.reason == "secret_suspect"


def test_write_gate_rejects_failed_executor_output() -> None:
    decision = evaluate_write_request(
        _validation_input(
            executor_status="failed",
            changed_files=(
                ProposedFileChange(
                    path="src/higgs_agent/validation/write_gate.py",
                    additions=5,
                    deletions=0,
                ),
            ),
        ),
        load_write_policy(Path("config/write-policy.example.json")),
    )

    assert decision.decision == "rejected"
    assert decision.reason == "executor_did_not_succeed"


def test_write_gate_rejects_when_no_changes_are_proposed() -> None:
    decision = evaluate_write_request(
        _validation_input(changed_files=()),
        load_write_policy(Path("config/write-policy.example.json")),
    )

    assert decision.decision == "rejected"
    assert decision.reason == "no_repository_mutation_proposed"


def test_write_gate_rejects_failed_validation_commands() -> None:
    decision = evaluate_write_request(
        _validation_input(
            changed_files=(
                ProposedFileChange(path="src/higgs_agent/runtime.py", additions=20, deletions=0),
            ),
            validation_passed=False,
        ),
        load_write_policy(Path("config/write-policy.example.json")),
    )

    assert decision.decision == "rejected"
    assert decision.reason == "validation_failed"


def test_write_policy_loader_rejects_missing_fields() -> None:
    with pytest.raises(ValueError, match="allowed_paths"):
        load_write_policy(Path("tests/Fixtures/config/write_policy_invalid_missing_allowed.json"))


def _validation_input(
    *,
    executor_status: str = "succeeded",
    output_text: str = "Sanitized output summary.",
    changed_files: tuple[ProposedFileChange, ...],
    validation_passed: bool = True,
) -> ValidationInput:
    return ValidationInput(
        ticket_id="T-000015",
        run_id="run-15",
        attempt_id="attempt-1",
        executor_status=executor_status,
        output_text=output_text,
        changed_files=changed_files,
        validation_summary="tests passed, write gate evaluated",
        validation_passed=validation_passed,
        usage=ProviderUsage(total_tokens=1800, cost_usd=0.92, latency_ms=4823),
    )