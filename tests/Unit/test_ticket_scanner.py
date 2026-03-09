from __future__ import annotations

from pathlib import Path

import yaml

from higgs_agent.tickets import (
    scan_ticket_directory,
    select_next_ready_ticket,
    select_ready_tickets,
)


def test_scanner_ignores_non_ticket_files_and_subdirectories(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    (tickets_dir / "archive").mkdir()

    _write_ticket(tickets_dir / "T-000100.md", id="T-000100", status="done", priority="p1")
    _write_ticket(
        tickets_dir / "archive" / "T-000099.md", id="T-000099", status="ready", priority="p0"
    )
    (tickets_dir / "last_ticket_id").write_text("T-000100\n")
    (tickets_dir / "ticket.template").write_text("template\n")

    result = scan_ticket_directory(tickets_dir)

    assert [ticket.id for ticket in result.tickets] == ["T-000100"]
    assert result.invalid == ()


def test_ready_selection_orders_by_priority_then_ticket_id(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()

    _write_ticket(tickets_dir / "T-000102.md", id="T-000102", status="ready", priority="p1")
    _write_ticket(tickets_dir / "T-000101.md", id="T-000101", status="ready", priority="p0")
    _write_ticket(tickets_dir / "T-000103.md", id="T-000103", status="ready", priority="p0")

    result = scan_ticket_directory(tickets_dir)

    assert [ticket.id for ticket in select_ready_tickets(result)] == [
        "T-000101",
        "T-000103",
        "T-000102",
    ]
    assert select_next_ready_ticket(result).id == "T-000101"


def test_scanner_blocks_unfinished_dependencies_and_reports_parse_errors(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()

    _write_ticket(tickets_dir / "T-000100.md", id="T-000100", status="done", priority="p2")
    _write_ticket(
        tickets_dir / "T-000101.md",
        id="T-000101",
        status="ready",
        priority="p0",
        depends_on=["T-000100"],
    )
    _write_ticket(tickets_dir / "T-000102.md", id="T-000102", status="claimed", priority="p0")
    _write_ticket(
        tickets_dir / "T-000103.md",
        id="T-000103",
        status="ready",
        priority="p1",
        depends_on=["T-000102"],
    )
    _write_ticket(
        tickets_dir / "T-000104.md",
        id="T-000104",
        status="ready",
        priority="p2",
        depends_on=["T-999999"],
    )
    (tickets_dir / "T-000105.md").write_text(
        "---\nid: T-000105\nstatus: ready\ndepends_on: T-000100\n---\n"
    )

    result = scan_ticket_directory(tickets_dir)

    assert result.decision_for("T-000101").reason == "ready"
    assert result.decision_for("T-000103").reason == "blocked_by_dependency:T-000102:claimed"
    assert result.decision_for("T-000104").reason == "missing_dependency:T-999999"
    assert [issue.path.name for issue in result.invalid] == ["T-000105.md"]
    assert [ticket.id for ticket in select_ready_tickets(result)] == ["T-000101"]


def _write_ticket(path: Path, **frontmatter: object) -> None:
    payload = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    path.write_text(f"---\n{payload}\n---\n\nBody\n")
