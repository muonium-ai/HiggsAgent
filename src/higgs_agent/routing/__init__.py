"""Routing-facing classification and policy surfaces."""

from .classifier import (
    ClassificationInputError,
    NormalizedTicketSemantics,
    classify_ticket,
)
from .policy import (
    RouteDecision,
    RouteGuardrails,
    RoutingInputError,
    choose_route,
    load_route_guardrails,
)

__all__ = [
    "ClassificationInputError",
    "NormalizedTicketSemantics",
    "RouteDecision",
    "RouteGuardrails",
    "RoutingInputError",
    "classify_ticket",
    "choose_route",
    "load_route_guardrails",
]
"""Routing normalization and selection."""
