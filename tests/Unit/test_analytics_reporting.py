from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from higgs_agent.analytics import (
    AnalyticsFilter,
    aggregate_attempt_summaries,
    build_ticket_metadata_index,
    load_attempt_summaries,
)
from higgs_agent.cli import main


def test_aggregate_attempt_summaries_supports_grouping_and_filters(tmp_path: Path, capsys) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    _write_ticket(
        tickets_dir / "T-000100.md",
        ticket_id="T-000100",
        ticket_type="code",
        priority="p1",
        platform="ios",
        complexity="high",
    )
    _write_ticket(
        tickets_dir / "T-000101.md",
        ticket_id="T-000101",
        ticket_type="docs",
        priority="p2",
        platform="web",
        complexity="low",
    )

    attempt_summaries_path = (
        tmp_path / ".higgs" / "local" / "analytics" / "attempt-summaries.ndjson"
    )
    attempt_summaries_path.parent.mkdir(parents=True)
    attempt_summaries_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "run_id": "run-1",
                        "attempt_id": "attempt-1",
                        "ticket_id": "T-000100",
                        "started_at": "2026-03-06T10:00:00Z",
                        "ended_at": "2026-03-06T10:00:05Z",
                        "duration_ms": 5000,
                        "final_result": "succeeded",
                        "provider": "openrouter",
                        "model": "anthropic/claude-sonnet-4",
                        "tool_call_count": 2,
                        "retry_count": 1,
                        "usage": {
                            "tokens_prompt": 100,
                            "tokens_completion": 40,
                            "total_tokens": 140,
                            "cost_usd": 0.04,
                            "latency_ms": 5000,
                        },
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "run_id": "run-2",
                        "attempt_id": "attempt-2",
                        "ticket_id": "T-000101",
                        "started_at": "2026-03-06T11:00:00Z",
                        "ended_at": "2026-03-06T11:00:03Z",
                        "duration_ms": 3000,
                        "final_result": "failed",
                        "provider": "openrouter",
                        "model": "anthropic/claude-sonnet-4",
                        "tool_call_count": 0,
                        "retry_count": 0,
                        "usage": {
                            "tokens_prompt": 60,
                            "tokens_completion": 20,
                            "total_tokens": 80,
                            "cost_usd": 0.02,
                            "latency_ms": 3000,
                        },
                        "error": {"kind": "provider", "message": "rate limit"},
                    }
                ),
            ]
        )
        + "\n"
    )

    summaries = load_attempt_summaries(attempt_summaries_path)
    metadata_index = build_ticket_metadata_index(tickets_dir)
    report = aggregate_attempt_summaries(
        summaries,
        metadata_index,
        AnalyticsFilter(
            provider="openrouter",
            start_at=None,
            end_at=None,
            group_by=("provider", "ticket_type"),
        ),
    )

    schema = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())
    assert len(report.records) == 2
    for record in report.records:
        jsonschema.validate(record, schema)

    assert report.records[0]["dimensions"]["provider"] == "openrouter"
    assert report.records[0]["metrics"]["attempts_total"] == 1
    assert report.records[1]["metrics"]["failure_rate"] in {0.0, 1.0}

    main(
        [
            "analytics",
            "report",
            "--attempt-summaries",
            str(attempt_summaries_path),
            "--tickets-dir",
            str(tickets_dir),
            "--group-by",
            "provider",
            "--group-by",
            "ticket_type",
        ]
    )
    output = capsys.readouterr().out
    assert "attempts" in output
    assert "openrouter" in output
    assert "code" in output


def test_cli_report_json_respects_time_window(tmp_path: Path, capsys) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    _write_ticket(
        tickets_dir / "T-000200.md",
        ticket_id="T-000200",
        ticket_type="code",
        priority="p0",
        platform="repo",
        complexity="medium",
    )

    attempt_summaries_path = (
        tmp_path / ".higgs" / "local" / "analytics" / "attempt-summaries.ndjson"
    )
    attempt_summaries_path.parent.mkdir(parents=True)
    attempt_summaries_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-3",
                "attempt_id": "attempt-3",
                "ticket_id": "T-000200",
                "started_at": "2026-03-06T12:00:00Z",
                "ended_at": "2026-03-06T12:00:01Z",
                "duration_ms": 1000,
                "final_result": "succeeded",
                "provider": "openrouter",
                "model": "anthropic/claude-sonnet-4",
                "tool_call_count": 1,
                "retry_count": 0,
                "usage": {
                    "tokens_prompt": 20,
                    "tokens_completion": 10,
                    "total_tokens": 30,
                    "cost_usd": 0.01,
                    "latency_ms": 1000,
                },
            }
        )
        + "\n"
    )

    main(
        [
            "analytics",
            "report",
            "--attempt-summaries",
            str(attempt_summaries_path),
            "--tickets-dir",
            str(tickets_dir),
            "--start-at",
            "2026-03-06T11:00:00Z",
            "--end-at",
            "2026-03-06T13:00:00Z",
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["window"]["granularity"] == "custom"
    assert output[0]["metrics"]["cost_usd_total"] == 0.01


def _write_ticket(
    path: Path,
    *,
    ticket_id: str,
    ticket_type: str,
    priority: str,
    platform: str,
    complexity: str,
) -> None:
    path.write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "status: done\n"
        f"type: {ticket_type}\n"
        f"priority: {priority}\n"
        "effort: m\n"
        "higgs_schema_version: 1\n"
        f"higgs_platform: {platform}\n"
        f"higgs_complexity: {complexity}\n"
        "higgs_execution_target: hosted\n"
        "higgs_tool_profile: standard\n"
        "---\n\n"
        "Body\n"
    )