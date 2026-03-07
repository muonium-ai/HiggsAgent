"""CLI entrypoints for HiggsAgent."""

from __future__ import annotations

import argparse
import os
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
from higgs_agent.bootstrap import BootstrapError, available_sample_projects, bootstrap_sample_project
from higgs_agent.runtime import RuntimeConfigError, parse_changed_file_spec, run_ticketed_project


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "analytics" and args.analytics_command == "report":
        _run_analytics_report(args)
        return

    if args.command == "bootstrap" and args.bootstrap_command == "sample-project":
        _run_bootstrap_sample_project(args)
        return

    if args.command == "run" and args.run_command == "ticketed-project":
        _run_ticketed_project(args)
        return

    raise SystemExit("HiggsAgent runtime is not implemented yet.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="higgs-agent")
    subparsers = parser.add_subparsers(dest="command")

    analytics_parser = subparsers.add_parser("analytics")
    analytics_subparsers = analytics_parser.add_subparsers(dest="analytics_command")

    bootstrap_parser = subparsers.add_parser("bootstrap")
    bootstrap_subparsers = bootstrap_parser.add_subparsers(dest="bootstrap_command")

    run_parser = subparsers.add_parser("run")
    run_subparsers = run_parser.add_subparsers(dest="run_command")

    sample_project_choices = available_sample_projects()
    sample_project_parser = bootstrap_subparsers.add_parser("sample-project")
    sample_project_parser.add_argument("target_dir", type=Path)
    sample_project_parser.add_argument(
        "--sample-project",
        default="game-of-life",
        choices=list(sample_project_choices) or None,
    )
    sample_project_parser.add_argument(
        "--higgsagent-repo-url",
        default="https://github.com/muonium-ai/HiggsAgent.git",
    )
    sample_project_parser.add_argument("--force", action="store_true")

    run_ticketed_project_parser = run_subparsers.add_parser("ticketed-project")
    run_ticketed_project_parser.add_argument("--repo-root", type=Path, default=Path("."))
    run_ticketed_project_parser.add_argument("--requirements", type=Path, required=True)
    run_ticketed_project_parser.add_argument("--tickets-dir", type=Path, required=True)
    run_ticketed_project_parser.add_argument("--guardrails", type=Path, required=True)
    run_ticketed_project_parser.add_argument("--write-policy", type=Path, required=True)
    run_ticketed_project_parser.add_argument(
        "--changed-file",
        action="append",
        required=True,
        help="PATH:ADDITIONS:DELETIONS[:binary]",
    )
    run_ticketed_project_parser.add_argument("--validation-summary", required=True)
    run_ticketed_project_parser.add_argument("--openrouter-api-key")

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


def _run_bootstrap_sample_project(args: argparse.Namespace) -> None:
    try:
        result = bootstrap_sample_project(
            target_dir=args.target_dir,
            sample_project=args.sample_project,
            higgsagent_repo_url=args.higgsagent_repo_url,
            force=args.force,
        )
    except BootstrapError as exc:
        raise SystemExit(f"bootstrap sample-project failed: {exc}") from exc

    print(f"created evaluation repo at {result.target_dir}")
    print(f"sample project: {result.sample_project_dir}")
    print(f"higgsagent submodule: {result.higgsagent_submodule_dir}")


def _run_ticketed_project(args: argparse.Namespace) -> None:
    try:
        repo_root = _require_directory_path(args.repo_root, flag_name="--repo-root")
        requirements_path = _require_file_path(args.requirements, flag_name="--requirements")
        tickets_dir = _require_directory_path(args.tickets_dir, flag_name="--tickets-dir")
        guardrails_path = _require_file_path(args.guardrails, flag_name="--guardrails")
        write_policy_path = _require_file_path(args.write_policy, flag_name="--write-policy")
        openrouter_api_key = args.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise RuntimeConfigError(
                "OpenRouter API key required via --openrouter-api-key or OPENROUTER_API_KEY"
            )
        changed_files = tuple(parse_changed_file_spec(spec) for spec in args.changed_file)
        outcome = run_ticketed_project(
            repo_root=repo_root,
            requirements_path=requirements_path,
            tickets_dir=tickets_dir,
            guardrails_path=guardrails_path,
            write_policy_path=write_policy_path,
            changed_files=changed_files,
            validation_summary=args.validation_summary,
            openrouter_api_key=openrouter_api_key,
        )
    except (FileNotFoundError, RuntimeConfigError, ValueError) as exc:
        raise SystemExit(f"run ticketed-project failed: {exc}") from exc

    print(f"ticket: {outcome.ticket.id}")
    print(f"provider: {outcome.route.provider or 'blocked'}")
    print(f"model: {outcome.route.model_id or 'blocked'}")
    print(f"execution_status: {outcome.execution_result.status}")
    print(f"validation_decision: {outcome.validation_decision.decision}")
    telemetry_paths = getattr(outcome.execution_result, "metadata", {}).get("telemetry_paths", {})
    if telemetry_paths:
        print(f"events_path: {telemetry_paths['events']}")
        print(f"artifacts_dir: {telemetry_paths['artifacts_dir']}")
        print(f"attempt_summaries_path: {telemetry_paths['attempt_summaries']}")
    if outcome.execution_result.output_text:
        print("output:")
        print(outcome.execution_result.output_text)


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