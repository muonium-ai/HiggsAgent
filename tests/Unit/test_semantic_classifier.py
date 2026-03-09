from __future__ import annotations

import pytest

from higgs_agent.routing import ClassificationInputError, classify_ticket
from higgs_agent.testing import load_markdown_frontmatter


def test_classifier_accepts_valid_fixture() -> None:
    semantics = classify_ticket(load_markdown_frontmatter("tickets/higgs_ticket_valid_minimal.md"))

    assert semantics.ticket_id == "T-900001"
    assert semantics.work_type == "code"
    assert semantics.priority == "p1"
    assert semantics.platform == "agnostic"
    assert semantics.complexity == "low"
    assert semantics.execution_target == "auto"
    assert semantics.tool_profile == "standard"
    assert semantics.warnings == ()


def test_classifier_normalizes_missing_transition_fields() -> None:
    semantics = classify_ticket(
        {
            "id": "T-123456",
            "type": "docs",
            "priority": "p0",
            "effort": "m",
            "labels": ["docs"],
            "tags": ["phase-1"],
        }
    )

    assert semantics.platform == "agnostic"
    assert semantics.complexity == "medium"
    assert semantics.execution_target == "auto"
    assert semantics.tool_profile == "standard"
    assert semantics.labels == ("docs",)
    assert semantics.tags == ("phase-1",)
    assert semantics.warnings == (
        "higgs_schema_version missing; normalized to 1",
        "higgs_platform missing; normalized to agnostic",
    )


def test_classifier_preserves_local_execution_target() -> None:
    semantics = classify_ticket(
        {
            "id": "T-123457",
            "type": "code",
            "priority": "p1",
            "effort": "s",
            "higgs_schema_version": 1,
            "higgs_platform": "repo",
            "higgs_execution_target": "local",
            "higgs_tool_profile": "none",
        }
    )

    assert semantics.execution_target == "local"
    assert semantics.tool_profile == "none"
    assert semantics.complexity == "low"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"id": "T-1", "priority": "p0", "higgs_platform": "agnostic"}, "type"),
        (
            {
                "id": "T-1",
                "type": "code",
                "priority": "p0",
                "higgs_schema_version": 1,
                "higgs_platform": "edge",
            },
            "higgs_platform",
        ),
        (
            {
                "id": "T-1",
                "type": "code",
                "priority": "p0",
                "higgs_schema_version": 1,
                "higgs_platform": "agnostic",
                "higgs_execution_target": "edge",
            },
            "higgs_execution_target",
        ),
        (
            {
                "id": "T-1",
                "type": "code",
                "priority": "urgent",
                "higgs_schema_version": 1,
                "higgs_platform": "agnostic",
            },
            "priority",
        ),
    ],
)
def test_classifier_rejects_invalid_inputs(payload: dict[str, object], message: str) -> None:
    with pytest.raises(ClassificationInputError, match=message):
        classify_ticket(payload)
