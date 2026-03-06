from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from higgs_agent.adaptive import (
    build_adaptive_snapshot_from_aggregate_records,
    select_adaptive_route,
)
from higgs_agent.analytics import (
    AnalyticsFilter,
    aggregate_attempt_summaries,
    build_ticket_metadata_index,
)
from higgs_agent.events.records import AttemptSummaryBuilder, EventStreamBuilder
from higgs_agent.providers.contract import ProviderUsage
from higgs_agent.routing import NormalizedTicketSemantics, RouteDecision


def test_adaptive_selection_payload_remains_observable_and_analytics_compatible(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    _write_ticket(tickets_dir / "T-000300.md")

    snapshot = build_adaptive_snapshot_from_aggregate_records(
        (
            {
                "dimensions": {"provider": "openrouter", "model": "openai/gpt-4o-mini"},
                "window": {"end_at": "2026-03-07T11:59:00Z"},
                "metrics": {
                    "attempts_total": 3,
                    "succeeded_count": 3,
                    "failed_count": 0,
                    "blocked_count": 0,
                    "retry_count_total": 0,
                    "tool_call_count_total": 0,
                    "duration_ms_total": 1800,
                    "total_tokens_total": 90,
                    "cost_usd_total": 0.09,
                },
            },
            {
                "dimensions": {"provider": "openrouter", "model": "openai/gpt-4o"},
                "window": {"end_at": "2026-03-07T11:59:00Z"},
                "metrics": {
                    "attempts_total": 2,
                    "succeeded_count": 1,
                    "failed_count": 1,
                    "blocked_count": 0,
                    "retry_count_total": 1,
                    "tool_call_count_total": 2,
                    "duration_ms_total": 4200,
                    "total_tokens_total": 220,
                    "cost_usd_total": 0.42,
                },
            },
        ),
        generated_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
        freshness_reference=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
    )

    selection = select_adaptive_route(
        _semantics(),
        (
            _candidate("openrouter", "openai/gpt-4o-mini", "economy", estimated_cost_usd=0.35),
            _candidate("openrouter", "openai/gpt-4o", "balanced", estimated_cost_usd=2.0),
        ),
        snapshot,
    )
    payload = selection.as_metadata_payload()

    assert selection.selected_route.model_id == "openai/gpt-4o-mini"
    assert payload["telemetry_source"] == "aggregate_records"
    assert payload["ranked_candidates"][0]["selected"] is True
    assert payload["ranked_candidates"][0]["used_deterministic_defaults"] is False
    assert any(
        item.startswith("success_rate:")
        for item in payload["ranked_candidates"][0]["explanation"]
    )
    json.dumps(payload)

    event = EventStreamBuilder(
        run_id="run-adaptive-1",
        attempt_id="attempt-adaptive-1",
        ticket_id="T-000300",
        executor_version="phase-4",
    ).append(
        "route.selected",
        "succeeded",
        payload={"adaptive_selection": payload},
    )
    _validate_event(event)

    attempt_summary = AttemptSummaryBuilder(
        run_id="run-adaptive-1",
        attempt_id="attempt-adaptive-1",
        ticket_id="T-000300",
        started_at="2026-03-07T12:00:00Z",
    ).build(
        final_result="succeeded",
        provider=selection.selected_route.provider,
        model=selection.selected_route.model_id,
        tool_call_count=0,
        retry_count=0,
        usage=ProviderUsage(
            tokens_prompt=40,
            tokens_completion=12,
            total_tokens=52,
            cost_usd=0.03,
            latency_ms=800,
        ),
        ended_at="2026-03-07T12:00:01Z",
    )
    _validate_attempt_summary(attempt_summary)

    report = aggregate_attempt_summaries(
        (attempt_summary,),
        build_ticket_metadata_index(tickets_dir),
        AnalyticsFilter(group_by=("provider", "model", "ticket_type")),
    )

    assert len(report.records) == 1
    _validate_aggregate(report.records[0])
    assert report.records[0]["dimensions"]["provider"] == "openrouter"
    assert report.records[0]["dimensions"]["model"] == "openai/gpt-4o-mini"
    assert report.records[0]["metrics"]["attempts_total"] == 1


def _semantics() -> NormalizedTicketSemantics:
    return NormalizedTicketSemantics(
        ticket_id="T-000300",
        work_type="docs",
        priority="p1",
        platform="agnostic",
        complexity="low",
        execution_target="auto",
        tool_profile="none",
        labels=(),
        tags=(),
        warnings=(),
    )


def _candidate(
    provider: str,
    model_id: str,
    route_family: str,
    *,
    estimated_cost_usd: float,
) -> RouteDecision:
    return RouteDecision(
        ticket_id="T-000300",
        priority="p1",
        selected=True,
        provider=provider,
        model_id=model_id,
        route_family=route_family,
        estimated_cost_usd=estimated_cost_usd,
        requires_tool_calls=False,
        blocked_reason=None,
        rationale=(f"selected_model:{model_id}",),
    )


def _validate_event(event: dict[str, object]) -> None:
    event_schema = json.loads(Path("schemas/execution-event.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = Registry().with_resource(
        common_defs["$id"],
        Resource.from_contents(common_defs),
    ).with_resource(
        "common-defs.schema.json",
        Resource.from_contents(common_defs),
    )
    jsonschema.Draft202012Validator(event_schema, registry=registry).validate(event)


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
    jsonschema.Draft202012Validator(summary_schema, registry=registry).validate(summary)


def _validate_aggregate(record: dict[str, object]) -> None:
    aggregate_schema = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())
    jsonschema.validate(record, aggregate_schema)


def _write_ticket(path: Path) -> None:
    path.write_text(
        "---\n"
        "id: T-000300\n"
        "status: done\n"
        "type: docs\n"
        "priority: p1\n"
        "effort: m\n"
        "higgs_schema_version: 1\n"
        "higgs_platform: agnostic\n"
        "higgs_complexity: low\n"
        "higgs_execution_target: auto\n"
        "higgs_tool_profile: none\n"
        "---\n\n"
        "Body\n"
    )