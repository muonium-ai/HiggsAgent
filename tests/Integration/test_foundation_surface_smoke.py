from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from higgs_agent.testing import load_json_fixture, load_markdown_frontmatter


def test_foundation_contracts_align() -> None:
    ticket_schema = json.loads(Path("schemas/higgs-ticket.schema.json").read_text())
    event_schema = json.loads(Path("schemas/execution-event.schema.json").read_text())
    attempt_schema = json.loads(Path("schemas/execution-attempt.schema.json").read_text())
    aggregate_schema = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())

    ticket = load_markdown_frontmatter("tickets/higgs_ticket_valid_minimal.md")
    event = load_json_fixture("events/execution_event_valid_minimal.json")
    attempt = load_json_fixture("events/execution_attempt_valid_minimal.json")
    aggregate = load_json_fixture("events/analytics_aggregate_valid_minimal.json")

    jsonschema.validate(ticket, ticket_schema)
    jsonschema.validate(event, event_schema)
    jsonschema.validate(attempt, attempt_schema)
    jsonschema.validate(aggregate, aggregate_schema)
    assert event["sequence"] == 0
    assert attempt["final_result"] == "succeeded"
    assert aggregate["metrics"]["attempts_total"] == 4
