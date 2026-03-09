from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

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


def test_aggregate_attempt_summaries_handles_local_partial_usage_without_billing(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    _write_ticket(
        tickets_dir / "T-000201.md",
        ticket_id="T-000201",
        ticket_type="docs",
        priority="p1",
        platform="repo",
        complexity="low",
        execution_target="local",
    )

    attempt_summaries_path = (
        tmp_path / ".higgs" / "local" / "analytics" / "attempt-summaries.ndjson"
    )
    attempt_summaries_path.parent.mkdir(parents=True)
    attempt_summaries_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-local-1",
                "attempt_id": "attempt-local-1",
                "ticket_id": "T-000201",
                "started_at": "2026-03-06T12:15:00Z",
                "ended_at": "2026-03-06T12:15:01Z",
                "duration_ms": 1000,
                "final_result": "succeeded",
                "provider": "local",
                "model": "local/llama3.1:8b",
                "tool_call_count": 0,
                "retry_count": 0,
                "usage": {
                    "tokens_prompt": 18,
                    "tokens_completion": 6,
                    "total_tokens": 24,
                    "latency_ms": 1000,
                },
            }
        )
        + "\n"
    )

    summaries = load_attempt_summaries(attempt_summaries_path)
    metadata_index = build_ticket_metadata_index(tickets_dir)
    report = aggregate_attempt_summaries(
        summaries,
        metadata_index,
        AnalyticsFilter(group_by=("provider", "model", "ticket_type")),
    )

    schema = json.loads(Path("schemas/analytics-aggregate.schema.json").read_text())
    assert len(report.records) == 1
    jsonschema.validate(report.records[0], schema)
    assert report.records[0]["dimensions"]["provider"] == "local"
    assert report.records[0]["dimensions"]["model"] == "local/llama3.1:8b"
    assert report.records[0]["metrics"]["cost_usd_total"] == 0.0
    assert report.records[0]["metrics"]["total_tokens_total"] == 24
    assert report.records[0]["source"]["export_safe"] is True


def test_bounded_aggregation_excludes_rows_with_missing_or_unusable_timestamps(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    _write_ticket(
        tickets_dir / "T-000210.md",
        ticket_id="T-000210",
        ticket_type="code",
        priority="p1",
        platform="repo",
        complexity="medium",
    )
    _write_ticket(
        tickets_dir / "T-000211.md",
        ticket_id="T-000211",
        ticket_type="code",
        priority="p1",
        platform="repo",
        complexity="medium",
    )
    _write_ticket(
        tickets_dir / "T-000212.md",
        ticket_id="T-000212",
        ticket_type="code",
        priority="p1",
        platform="repo",
        complexity="medium",
    )

    summaries = (
        {
            "ticket_id": "T-000210",
            "started_at": "2026-03-06T12:00:00Z",
            "ended_at": "2026-03-06T12:00:01Z",
            "final_result": "succeeded",
            "provider": "openrouter",
            "model": "anthropic/claude-sonnet-4",
            "usage": {"cost_usd": 0.01},
        },
        {
            "ticket_id": "T-000211",
            "ended_at": "2026-03-06T12:05:01Z",
            "final_result": "succeeded",
            "provider": "openrouter",
            "model": "anthropic/claude-sonnet-4",
            "usage": {"cost_usd": 0.02},
        },
        {
            "ticket_id": "T-000212",
            "started_at": 123,
            "ended_at": "2026-03-06T12:10:01Z",
            "final_result": "succeeded",
            "provider": "openrouter",
            "model": "anthropic/claude-sonnet-4",
            "usage": {"cost_usd": 0.03},
        },
    )

    metadata_index = build_ticket_metadata_index(tickets_dir)
    report = aggregate_attempt_summaries(
        summaries,
        metadata_index,
        AnalyticsFilter(
            start_at=datetime(2026, 3, 6, 11, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 6, 13, 0, tzinfo=UTC),
            group_by=("provider",),
        ),
    )

    assert len(report.records) == 1
    assert report.records[0]["metrics"]["attempts_total"] == 1
    assert report.records[0]["metrics"]["cost_usd_total"] == 0.01


def test_build_ticket_metadata_index_skips_malformed_ticket_files(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    archive_dir = tickets_dir / "archive"
    archive_dir.mkdir()
    _write_ticket(
        tickets_dir / "T-000230.md",
        ticket_id="T-000230",
        ticket_type="code",
        priority="p0",
        platform="repo",
        complexity="high",
    )
    _write_ticket(
        archive_dir / "T-000231.md",
        ticket_id="T-000231",
        ticket_type="docs",
        priority="p2",
        platform="web",
        complexity="low",
    )
    (tickets_dir / "T-000232.md").write_text("not-frontmatter\n")
    (archive_dir / "T-000233.md").write_text(
        "---\nid: T-000233\nstatus: done\ndepends_on: nope\n---\n"
    )

    metadata_index = build_ticket_metadata_index(tickets_dir)

    assert set(metadata_index) == {"T-000230", "T-000231"}
    assert metadata_index["T-000230"]["ticket_priority"] == "p0"
    assert metadata_index["T-000231"]["ticket_type"] == "docs"


def test_cli_report_fails_for_missing_attempt_summaries_file(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()

    with pytest.raises(
        SystemExit, match=r"analytics report failed: --attempt-summaries path not found"
    ):
        main(
            [
                "analytics",
                "report",
                "--attempt-summaries",
                str(tmp_path / "missing.ndjson"),
                "--tickets-dir",
                str(tickets_dir),
            ]
        )


def test_cli_report_json_excludes_rows_with_incomplete_timestamps_when_bounded(
    tmp_path: Path, capsys
) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    _write_ticket(
        tickets_dir / "T-000220.md",
        ticket_id="T-000220",
        ticket_type="code",
        priority="p1",
        platform="repo",
        complexity="medium",
    )
    _write_ticket(
        tickets_dir / "T-000221.md",
        ticket_id="T-000221",
        ticket_type="code",
        priority="p1",
        platform="repo",
        complexity="medium",
    )

    attempt_summaries_path = tmp_path / "attempt-summaries.ndjson"
    attempt_summaries_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "run_id": "run-valid",
                        "attempt_id": "attempt-valid",
                        "ticket_id": "T-000220",
                        "started_at": "2026-03-06T12:00:00Z",
                        "ended_at": "2026-03-06T12:00:01Z",
                        "final_result": "succeeded",
                        "provider": "openrouter",
                        "model": "anthropic/claude-sonnet-4",
                        "usage": {"cost_usd": 0.01},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "run_id": "run-missing-start",
                        "attempt_id": "attempt-missing-start",
                        "ticket_id": "T-000221",
                        "ended_at": "2026-03-06T12:00:02Z",
                        "final_result": "succeeded",
                        "provider": "openrouter",
                        "model": "anthropic/claude-sonnet-4",
                        "usage": {"cost_usd": 0.02},
                    }
                ),
            ]
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
            "--group-by",
            "provider",
            "--format",
            "json",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["metrics"]["attempts_total"] == 1
    assert output[0]["metrics"]["cost_usd_total"] == 0.01


def test_cli_report_fails_for_invalid_tickets_dir(tmp_path: Path) -> None:
    attempt_summaries_path = tmp_path / "attempt-summaries.ndjson"
    attempt_summaries_path.write_text("\n")

    with pytest.raises(SystemExit, match=r"analytics report failed: --tickets-dir path not found"):
        main(
            [
                "analytics",
                "report",
                "--attempt-summaries",
                str(attempt_summaries_path),
                "--tickets-dir",
                str(tmp_path / "missing-tickets"),
            ]
        )


def test_cli_report_fails_for_invalid_start_datetime(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    attempt_summaries_path = tmp_path / "attempt-summaries.ndjson"
    attempt_summaries_path.write_text("\n")

    with pytest.raises(
        SystemExit, match=r"analytics report failed: invalid ISO 8601 datetime for --start-at"
    ):
        main(
            [
                "analytics",
                "report",
                "--attempt-summaries",
                str(attempt_summaries_path),
                "--tickets-dir",
                str(tickets_dir),
                "--start-at",
                "not-a-datetime",
            ]
        )


def test_cli_report_fails_for_malformed_attempt_summary_json(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    attempt_summaries_path = tmp_path / "attempt-summaries.ndjson"
    attempt_summaries_path.write_text("{not-json}\n")

    with pytest.raises(
        SystemExit, match=r"analytics report failed: invalid JSON in attempt summaries"
    ):
        main(
            [
                "analytics",
                "report",
                "--attempt-summaries",
                str(attempt_summaries_path),
                "--tickets-dir",
                str(tickets_dir),
            ]
        )


def test_cli_report_ignores_malformed_ticket_metadata_files(tmp_path: Path, capsys) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    (tickets_dir / "T-000999.md").write_text("not-frontmatter\n")
    attempt_summaries_path = tmp_path / "attempt-summaries.ndjson"
    attempt_summaries_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-bad-ticket",
                "attempt_id": "attempt-bad-ticket",
                "ticket_id": "T-000999",
                "started_at": "2026-03-06T12:00:00Z",
                "ended_at": "2026-03-06T12:00:01Z",
                "final_result": "succeeded",
                "provider": "openrouter",
                "model": "anthropic/claude-sonnet-4",
                "usage": {},
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
            "--format",
            "json",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["metrics"]["attempts_total"] == 1
    assert output[0]["dimensions"] == {}


def _write_ticket(
    path: Path,
    *,
    ticket_id: str,
    ticket_type: str,
    priority: str,
    platform: str,
    complexity: str,
    execution_target: str = "hosted",
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
        f"higgs_execution_target: {execution_target}\n"
        "higgs_tool_profile: standard\n"
        "---\n\n"
        "Body\n"
    )
