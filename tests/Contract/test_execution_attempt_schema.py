from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from higgs_agent.testing import load_json_fixture

SCHEMA = json.loads(Path("schemas/execution-attempt.schema.json").read_text())


def test_valid_execution_attempt_fixture() -> None:
    payload = load_json_fixture("events/execution_attempt_valid_minimal.json")
    jsonschema.validate(payload, SCHEMA)


def test_missing_final_result_fails_validation() -> None:
    payload = load_json_fixture("events/execution_attempt_invalid_missing_final_result.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)


def test_negative_duration_fails_validation() -> None:
    payload = load_json_fixture("events/execution_attempt_invalid_negative_duration.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)