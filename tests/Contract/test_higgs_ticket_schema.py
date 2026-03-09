from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from higgs_agent.testing import load_markdown_frontmatter

SCHEMA = json.loads(Path("schemas/higgs-ticket.schema.json").read_text())


def test_valid_higgs_ticket_fixture() -> None:
    payload = load_markdown_frontmatter("tickets/higgs_ticket_valid_minimal.md")
    jsonschema.validate(payload, SCHEMA)


def test_missing_platform_fails_validation() -> None:
    payload = load_markdown_frontmatter("tickets/higgs_ticket_invalid_missing_platform.md")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)


def test_unknown_execution_target_fails_validation() -> None:
    payload = load_markdown_frontmatter("tickets/higgs_ticket_invalid_unknown_execution_target.md")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)
