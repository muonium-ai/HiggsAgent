from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from higgs_agent.testing import load_json_fixture

SCHEMA = json.loads(Path("schemas/execution-event.schema.json").read_text())


def test_valid_execution_event_fixture() -> None:
    payload = load_json_fixture("events/execution_event_valid_minimal.json")
    jsonschema.validate(payload, SCHEMA)


def test_missing_status_fails_validation() -> None:
    payload = load_json_fixture("events/execution_event_invalid_missing_status.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)


def test_unknown_event_type_fails_validation() -> None:
    payload = load_json_fixture("events/execution_event_invalid_unknown_event_type.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)