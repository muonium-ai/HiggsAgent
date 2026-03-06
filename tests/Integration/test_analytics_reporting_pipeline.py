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
from higgs_agent.testing import load_text_fixture


def test_analytics_pipeline_covers_failure_retry_and_redaction(tmp_path: Path, capsys) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    _write_ticket(
        tickets_dir / "T-000300.md",
        ticket_id="T-000300",
        ticket_type="code",
        priority="p0",
        platform="ios",
        complexity="high",
    )
    _write_ticket(
        tickets_dir / "T-000301.md",
        ticket_id="T-000301",
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
        load_text_fixture("events/analytics_attempt_summaries_pipeline.ndjson")
    )

    summaries = load_attempt_summaries(attempt_summaries_path)
    metadata_index = build_ticket_metadata_index(tickets_dir)
    report = aggregate_attempt_summaries(
        summaries,
        metadata_index,
        AnalyticsFilter(group_by=("provider", "ticket_type")),
    )

    schema = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())
    assert len(report.records) == 2
    for record in report.records:
        jsonschema.validate(record, schema)

    code_record = next(
        record for record in report.records if record["dimensions"]["ticket_type"] == "code"
    )
    docs_record = next(
        record for record in report.records if record["dimensions"]["ticket_type"] == "docs"
    )

    assert code_record["metrics"]["attempts_total"] == 2
    assert code_record["metrics"]["retried_attempt_count"] == 1
    assert code_record["metrics"]["retry_count_total"] == 2
    assert code_record["metrics"]["failed_count"] == 1
    assert code_record["metrics"]["error_kind_counts"]["provider"] == 1

    assert docs_record["source"]["export_safe"] is False
    json_output = json.dumps(report.records)
    assert "sk-live-secret" not in json_output
    assert "Bearer super-secret-token" not in json_output
    assert "raw prompt should not escape" not in json_output

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
            "--format",
            "json",
        ]
    )
    cli_output = capsys.readouterr().out
    assert "sk-live-secret" not in cli_output
    assert "raw prompt should not escape" not in cli_output
    rendered = json.loads(cli_output)
    assert any(record["source"]["export_safe"] is False for record in rendered)


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