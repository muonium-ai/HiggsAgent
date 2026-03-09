from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from higgs_agent.testing import load_json_fixture

SCHEMA = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())


def test_valid_analytics_aggregate_fixture() -> None:
    payload = load_json_fixture("events/analytics_aggregate_valid_minimal.json")
    jsonschema.validate(payload, SCHEMA)


def test_invalid_rate_fails_validation() -> None:
    payload = load_json_fixture("events/analytics_aggregate_invalid_rate.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)


def test_invalid_error_kind_bucket_fails_validation() -> None:
    payload = load_json_fixture("events/analytics_aggregate_invalid_error_kind_counts.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)
