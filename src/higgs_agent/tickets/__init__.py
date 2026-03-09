"""Ticket loading and eligibility logic."""

from .scanner import (
    TicketParseError,
    TicketRecord,
    TicketScanDecision,
    TicketScanIssue,
    TicketScanResult,
    discover_ticket_files,
    scan_ticket_directory,
    select_next_ready_ticket,
    select_ready_tickets,
)

__all__ = [
    "TicketParseError",
    "TicketRecord",
    "TicketScanDecision",
    "TicketScanIssue",
    "TicketScanResult",
    "discover_ticket_files",
    "scan_ticket_directory",
    "select_next_ready_ticket",
    "select_ready_tickets",
]
