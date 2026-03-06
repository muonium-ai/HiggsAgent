"""Application orchestration layer."""

from .dispatcher import DispatchOutcome, dispatch_next_ready_ticket

__all__ = ["DispatchOutcome", "dispatch_next_ready_ticket"]