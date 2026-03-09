"""Ticket discovery and ready-ticket selection for deterministic dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast

import yaml

DONE_STATUS = "done"
READY_STATUS = "ready"
PRIORITY_ORDER = {"p0": 0, "p1": 1, "p2": 2}


class TicketParseError(ValueError):
    """Raised when a ticket file does not satisfy the scanner boundary."""


@dataclass(frozen=True, slots=True)
class TicketRecord:
    """Parsed ticket record used by scanner and later dispatcher stages."""

    path: Path
    frontmatter: dict[str, Any]
    body: str

    @classmethod
    def from_path(cls, path: Path) -> TicketRecord:
        frontmatter, body = _parse_ticket_file(path)
        _validate_frontmatter(path, frontmatter)
        ticket_id = cast(str, frontmatter["id"])
        if ticket_id != path.stem:
            raise TicketParseError(
                f"{path}: frontmatter id '{ticket_id}' does not match filename '{path.stem}'"
            )
        return cls(path=path, frontmatter=frontmatter, body=body)

    @property
    def id(self) -> str:
        return cast(str, self.frontmatter["id"])

    @property
    def status(self) -> str:
        return cast(str, self.frontmatter["status"])

    @property
    def priority(self) -> str:
        return cast(str, self.frontmatter.get("priority", "p2"))

    @property
    def depends_on(self) -> tuple[str, ...]:
        return tuple(cast(list[str], self.frontmatter.get("depends_on", [])))


@dataclass(frozen=True, slots=True)
class TicketScanIssue:
    """Malformed ticket input discovered during directory scanning."""

    path: Path
    message: str


@dataclass(frozen=True, slots=True)
class TicketScanDecision:
    """Eligibility decision for a parsed ticket."""

    ticket_id: str
    path: Path
    eligible: bool
    reason: str


@dataclass(frozen=True, slots=True)
class TicketScanResult:
    """Scanner output separated into parsed tickets, invalid inputs, and decisions."""

    tickets: tuple[TicketRecord, ...]
    invalid: tuple[TicketScanIssue, ...]
    decisions: tuple[TicketScanDecision, ...]

    def decision_for(self, ticket_id: str) -> TicketScanDecision | None:
        for decision in self.decisions:
            if decision.ticket_id == ticket_id:
                return decision
        return None


def discover_ticket_files(tickets_dir: Path) -> tuple[Path, ...]:
    """Return top-level ticket markdown files in deterministic filename order."""

    return tuple(sorted(path for path in tickets_dir.glob("T-*.md") if path.is_file()))


def scan_ticket_directory(tickets_dir: Path) -> TicketScanResult:
    """Parse ticket files and evaluate ready-ticket eligibility."""

    parsed_records: list[TicketRecord] = []
    invalid: list[TicketScanIssue] = []
    seen_ids: set[str] = set()

    for path in discover_ticket_files(tickets_dir):
        try:
            record = TicketRecord.from_path(path)
        except TicketParseError as exc:
            invalid.append(TicketScanIssue(path=path, message=str(exc)))
            continue

        if record.id in seen_ids:
            invalid.append(TicketScanIssue(path=path, message=f"duplicate ticket id: {record.id}"))
            continue

        seen_ids.add(record.id)
        parsed_records.append(record)

    parsed_records.sort(key=lambda record: record.id)
    ticket_index = {record.id: record for record in parsed_records}
    decisions = tuple(_evaluate_ticket(record, ticket_index) for record in parsed_records)

    return TicketScanResult(
        tickets=tuple(parsed_records),
        invalid=tuple(invalid),
        decisions=decisions,
    )


def select_ready_tickets(scan_result: TicketScanResult) -> tuple[TicketRecord, ...]:
    """Return eligible ready tickets in deterministic dispatch order."""

    ready_ids = {decision.ticket_id for decision in scan_result.decisions if decision.eligible}
    selected = [record for record in scan_result.tickets if record.id in ready_ids]
    selected.sort(key=lambda record: (PRIORITY_ORDER.get(record.priority, 99), record.id))
    return tuple(selected)


def select_next_ready_ticket(scan_result: TicketScanResult) -> TicketRecord | None:
    """Return the next ready ticket, if one exists."""

    ready_tickets = select_ready_tickets(scan_result)
    if not ready_tickets:
        return None
    return ready_tickets[0]


def _evaluate_ticket(
    record: TicketRecord, ticket_index: Mapping[str, TicketRecord]
) -> TicketScanDecision:
    if record.status != READY_STATUS:
        return TicketScanDecision(
            ticket_id=record.id,
            path=record.path,
            eligible=False,
            reason=f"status:{record.status}",
        )

    for dependency_id in record.depends_on:
        dependency = ticket_index.get(dependency_id)
        if dependency is None:
            return TicketScanDecision(
                ticket_id=record.id,
                path=record.path,
                eligible=False,
                reason=f"missing_dependency:{dependency_id}",
            )

        if dependency.status != DONE_STATUS:
            return TicketScanDecision(
                ticket_id=record.id,
                path=record.path,
                eligible=False,
                reason=f"blocked_by_dependency:{dependency_id}:{dependency.status}",
            )

    return TicketScanDecision(
        ticket_id=record.id,
        path=record.path,
        eligible=True,
        reason="ready",
    )


def _parse_ticket_file(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text()
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise TicketParseError(f"{path}: missing YAML frontmatter")

    frontmatter = yaml.safe_load(parts[1])
    if not isinstance(frontmatter, dict):
        raise TicketParseError(f"{path}: frontmatter must be a mapping")

    return frontmatter, parts[2].lstrip("\n")


def _validate_frontmatter(path: Path, frontmatter: dict[str, Any]) -> None:
    for required_field in ("id", "status"):
        value = frontmatter.get(required_field)
        if not isinstance(value, str) or not value:
            raise TicketParseError(f"{path}: missing or invalid '{required_field}' field")

    depends_on = frontmatter.get("depends_on", [])
    if depends_on is None:
        frontmatter["depends_on"] = []
        depends_on = []
    if not isinstance(depends_on, list) or not all(isinstance(item, str) for item in depends_on):
        raise TicketParseError(f"{path}: 'depends_on' must be a list of ticket ids")

    priority = frontmatter.get("priority", "p2")
    if not isinstance(priority, str):
        raise TicketParseError(f"{path}: 'priority' must be a string when present")
