"""Routing-facing classification and policy surfaces."""

from .classifier import (
	ClassificationInputError,
	NormalizedTicketSemantics,
	classify_ticket,
)

__all__ = [
	"ClassificationInputError",
	"NormalizedTicketSemantics",
	"classify_ticket",
]
"""Routing normalization and selection."""