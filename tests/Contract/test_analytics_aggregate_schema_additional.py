from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from higgs_agent.testing import load_json_fixture

SCHEMA = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())


def test_missing_required_metric_field_fails_validation() -> None:
    payload = load_json_fixture("events/analytics_aggregate_invalid_missing_metric.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)