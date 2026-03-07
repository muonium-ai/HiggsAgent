"""CLI entrypoints for HiggsAgent."""

from __future__ import annotations

import argparse
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Sequence

from higgs_agent.analytics import (
    AnalyticsFilter,
    aggregate_attempt_summaries,
    build_ticket_metadata_index,
    load_attempt_summaries,
    render_report_table,
)


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "analytics" and args.analytics_command == "report":
        _run_analytics_report(args)
        return

    raise SystemExit("HiggsAgent runtime is not implemented yet.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="higgs-agent")
    subparsers = parser.add_subparsers(dest="command")

    analytics_parser = subparsers.add_parser("analytics")
    analytics_subparsers = analytics_parser.add_subparsers(dest="analytics_command")

    report_parser = analytics_subparsers.add_parser("report")
    report_parser.add_argument(
        "--attempt-summaries",
        type=Path,
        default=Path(".higgs/local/analytics/attempt-summaries.ndjson"),
    )
    report_parser.add_argument("--tickets-dir", type=Path, default=Path("tickets"))
    report_parser.add_argument(
        "--group-by",
        action="append",
        default=[],
        choices=[
            "provider",
            "model",
            "ticket_type",
            "ticket_priority",
            "higgs_platform",
            "higgs_complexity",
            "final_result",
            "error_kind",
        ],
    )
    report_parser.add_argument("--provider")
    report_parser.add_argument("--model")
    report_parser.add_argument("--ticket-type")
    report_parser.add_argument("--priority")
    report_parser.add_argument("--platform")
    report_parser.add_argument("--complexity")
    report_parser.add_argument("--result")
    report_parser.add_argument("--start-at")
    report_parser.add_argument("--end-at")
    report_parser.add_argument("--format", choices=["table", "json"], default="table")

    return parser


def _run_analytics_report(args: argparse.Namespace) -> None:
    try:
        attempt_summaries_path = _require_file_path(
            args.attempt_summaries,
            flag_name="--attempt-summaries",
        )
        tickets_dir = _require_directory_path(args.tickets_dir, flag_name="--tickets-dir")
        summaries = load_attempt_summaries(attempt_summaries_path)
        ticket_metadata_index = build_ticket_metadata_index(tickets_dir)
        analytics_filter = AnalyticsFilter(
            provider=args.provider,
            model=args.model,
            ticket_type=args.ticket_type,
            ticket_priority=args.priority,
            higgs_platform=args.platform,
            higgs_complexity=args.complexity,
            final_result=args.result,
            start_at=_parse_optional_datetime(args.start_at, flag_name="--start-at"),
            end_at=_parse_optional_datetime(args.end_at, flag_name="--end-at"),
            group_by=tuple(args.group_by),
        )
        report = aggregate_attempt_summaries(summaries, ticket_metadata_index, analytics_filter)
    except FileNotFoundError as exc:
        raise SystemExit(f"analytics report failed: {exc}") from exc
    except JSONDecodeError as exc:
        raise SystemExit(f"analytics report failed: invalid JSON in attempt summaries: {exc}") from exc
    except ValueError as exc:
        raise SystemExit(f"analytics report failed: {exc}") from exc

    if args.format == "json":
        print(report.to_json())
        return
    print(render_report_table(report))


def _parse_optional_datetime(value: str | None, *, flag_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO 8601 datetime for {flag_name}: {value!r}") from exc


def _require_file_path(path: Path, *, flag_name: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{flag_name} path not found: {path}")
    if not path.is_file():
        raise ValueError(f"{flag_name} must be a file: {path}")
    return path


def _require_directory_path(path: Path, *, flag_name: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{flag_name} path not found: {path}")
    if not path.is_dir():
        raise ValueError(f"{flag_name} must be a directory: {path}")
    return path