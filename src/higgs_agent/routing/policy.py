"""Deterministic hybrid routing policy for hosted and local model selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .classifier import NormalizedTicketSemantics


@dataclass(frozen=True, slots=True)
class RouteGuardrails:
    """Routing-relevant execution limits loaded from guardrail configuration."""

    max_cost_usd: float
    max_tool_calls: int
    economy_route: RouteProfile
    balanced_route: RouteProfile
    deep_route: RouteProfile
    local_route: RouteProfile


@dataclass(frozen=True, slots=True)
class RouteProfile:
    """Provider route profile available to the deterministic router."""

    provider: str
    model_id: str
    route_family: str
    estimated_cost_usd: float
    supports_extended_tools: bool
    supports_platform_sensitive_work: bool


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Explainable routing result consumed by the executor boundary."""

    ticket_id: str
    priority: str
    selected: bool
    provider: str | None
    model_id: str | None
    route_family: str | None
    estimated_cost_usd: float | None
    requires_tool_calls: bool
    blocked_reason: str | None
    rationale: tuple[str, ...]


class RoutingInputError(ValueError):
    """Raised when routing inputs or guardrail configuration are invalid."""


MINI_ROUTE = RouteProfile(
    provider="openrouter",
    model_id="openai/gpt-4o-mini",
    route_family="economy",
    estimated_cost_usd=0.35,
    supports_extended_tools=False,
    supports_platform_sensitive_work=False,
)
BALANCED_ROUTE = RouteProfile(
    provider="openrouter",
    model_id="openai/gpt-4o",
    route_family="balanced",
    estimated_cost_usd=2.0,
    supports_extended_tools=True,
    supports_platform_sensitive_work=True,
)
DEEP_ROUTE = RouteProfile(
    provider="openrouter",
    model_id="anthropic/claude-3.5-sonnet",
    route_family="deep",
    estimated_cost_usd=4.5,
    supports_extended_tools=True,
    supports_platform_sensitive_work=False,
)
LOCAL_ROUTE = RouteProfile(
    provider="local",
    model_id="local/llama3.1:8b",
    route_family="local",
    estimated_cost_usd=0.0,
    supports_extended_tools=False,
    supports_platform_sensitive_work=False,
)


def load_route_guardrails(config_path: Path) -> RouteGuardrails:
    """Load the subset of guardrail config used by the routing policy."""

    payload = json.loads(config_path.read_text())
    limits = payload.get("limits")
    if not isinstance(limits, dict):
        raise RoutingInputError("guardrail config missing 'limits' object")

    max_cost_usd = limits.get("max_cost_usd")
    max_tool_calls = limits.get("max_tool_calls")
    if not isinstance(max_cost_usd, int | float):
        raise RoutingInputError("guardrail config missing numeric 'max_cost_usd'")
    if not isinstance(max_tool_calls, int):
        raise RoutingInputError("guardrail config missing integer 'max_tool_calls'")

    routing_payload = payload.get("routing")
    if routing_payload is not None and not isinstance(routing_payload, dict):
        raise RoutingInputError("guardrail config 'routing' must be an object")

    return RouteGuardrails(
        max_cost_usd=float(max_cost_usd),
        max_tool_calls=max_tool_calls,
        economy_route=_load_route_profile(routing_payload, "economy", MINI_ROUTE),
        balanced_route=_load_route_profile(routing_payload, "balanced", BALANCED_ROUTE),
        deep_route=_load_route_profile(routing_payload, "deep", DEEP_ROUTE),
        local_route=_load_route_profile(routing_payload, "local", LOCAL_ROUTE),
    )


def choose_route(
    semantics: NormalizedTicketSemantics,
    guardrails: RouteGuardrails,
    *,
    local_execution_enabled: bool = False,
) -> RouteDecision:
    """Choose an explainable hybrid route or return an explicit block."""

    rationale: list[str] = [
        f"work_type:{semantics.work_type}",
        f"priority:{semantics.priority}",
        f"platform:{semantics.platform}",
        f"complexity:{semantics.complexity}",
        f"execution_target:{semantics.execution_target}",
        f"tool_profile:{semantics.tool_profile}",
        f"max_cost_usd:{guardrails.max_cost_usd:.2f}",
        f"local_execution_enabled:{str(local_execution_enabled).lower()}",
    ]

    if semantics.execution_target == "local":
        if not local_execution_enabled:
            rationale.append("blocked:local_runtime_unavailable")
            return _blocked_route(semantics, rationale, "local_execution_not_configured")
        if semantics.tool_profile != "none":
            rationale.append("blocked:local_route_requires_toolless_request")
            return _blocked_route(semantics, rationale, "local_execution_requires_toolless_route")
        rationale.append("hybrid_policy:explicit_local_route")
        return _selected_route(semantics, guardrails.local_route, rationale)

    if semantics.execution_target == "auto" and local_execution_enabled:
        auto_local_rationale = _auto_local_rationale(semantics)
        rationale.extend(auto_local_rationale)
        if auto_local_rationale[-1] == "hybrid_policy:auto_prefers_local":
            return _selected_route(semantics, guardrails.local_route, rationale)
    elif semantics.execution_target == "auto":
        rationale.append("hybrid_policy:auto_hosted_local_unavailable")
    else:
        rationale.append("hybrid_policy:explicit_hosted_route")

    return _choose_hosted_route(semantics, guardrails, rationale)


def _choose_hosted_route(
    semantics: NormalizedTicketSemantics,
    guardrails: RouteGuardrails,
    rationale: list[str],
) -> RouteDecision:
    candidates = _candidate_routes(semantics, guardrails, rationale)
    candidates = _filter_tool_profile(candidates, semantics, rationale)

    affordable = [
        route for route in candidates if route.estimated_cost_usd <= guardrails.max_cost_usd
    ]
    if not affordable:
        rationale.append("blocked:budget_exceeded_for_all_routes")
        return _blocked_route(semantics, rationale, "no_route_within_cost_ceiling")

    selected_route = affordable[0]
    if selected_route is not candidates[0]:
        rationale.append(f"budget_fallback:{candidates[0].model_id}->{selected_route.model_id}")
    return _selected_route(semantics, selected_route, rationale)


def _auto_local_rationale(semantics: NormalizedTicketSemantics) -> list[str]:
    if semantics.tool_profile != "none":
        return ["hybrid_policy:auto_hosted_due_tool_profile"]
    if semantics.platform not in {"agnostic", "repo"}:
        return ["hybrid_policy:auto_hosted_due_platform"]
    if semantics.work_type in {"docs", "chore", "spec"} and semantics.complexity != "high":
        return ["hybrid_policy:auto_local_for_low_risk_ticket", "hybrid_policy:auto_prefers_local"]
    return ["hybrid_policy:auto_hosted_due_capability_preference"]


def _selected_route(
    semantics: NormalizedTicketSemantics,
    selected_route: RouteProfile,
    rationale: list[str],
) -> RouteDecision:
    rationale.append(f"selected_model:{selected_route.model_id}")
    rationale.append(f"selected_family:{selected_route.route_family}")
    return RouteDecision(
        ticket_id=semantics.ticket_id,
        priority=semantics.priority,
        selected=True,
        provider=selected_route.provider,
        model_id=selected_route.model_id,
        route_family=selected_route.route_family,
        estimated_cost_usd=selected_route.estimated_cost_usd,
        requires_tool_calls=semantics.tool_profile != "none",
        blocked_reason=None,
        rationale=tuple(rationale),
    )


def _blocked_route(
    semantics: NormalizedTicketSemantics,
    rationale: list[str],
    blocked_reason: str,
) -> RouteDecision:
    return RouteDecision(
        ticket_id=semantics.ticket_id,
        priority=semantics.priority,
        selected=False,
        provider=None,
        model_id=None,
        route_family=None,
        estimated_cost_usd=None,
        requires_tool_calls=semantics.tool_profile != "none",
        blocked_reason=blocked_reason,
        rationale=tuple(rationale),
    )


def _candidate_routes(
    semantics: NormalizedTicketSemantics,
    guardrails: RouteGuardrails,
    rationale: list[str],
) -> list[RouteProfile]:
    if semantics.platform in {"ios", "macos"}:
        rationale.append("platform_bias:openai_platform_sensitive")
        candidates = [guardrails.balanced_route, guardrails.deep_route, guardrails.economy_route]
    elif semantics.work_type in {"code", "refactor"}:
        rationale.append("work_type_bias:deep_code_route")
        candidates = [guardrails.deep_route, guardrails.balanced_route, guardrails.economy_route]
    elif semantics.work_type in {"spec", "tests"}:
        rationale.append("work_type_bias:balanced_analysis_route")
        candidates = [guardrails.balanced_route, guardrails.deep_route, guardrails.economy_route]
    elif semantics.work_type in {"docs", "chore"}:
        rationale.append("work_type_bias:economy_docs_route")
        candidates = [guardrails.economy_route, guardrails.balanced_route, guardrails.deep_route]
    else:
        rationale.append("work_type_bias:default_balanced_route")
        candidates = [guardrails.balanced_route, guardrails.economy_route, guardrails.deep_route]

    if semantics.complexity == "high":
        rationale.append("complexity_bias:prefer_higher_capability")
        candidates = _promote_route_depth(candidates)

    return candidates


def _filter_tool_profile(
    candidates: list[RouteProfile],
    semantics: NormalizedTicketSemantics,
    rationale: list[str],
) -> list[RouteProfile]:
    if semantics.tool_profile == "extended":
        rationale.append("tool_profile_filter:extended")
        return [route for route in candidates if route.supports_extended_tools]

    if semantics.tool_profile == "none":
        rationale.append("tool_profile_filter:none")
        return candidates

    rationale.append("tool_profile_filter:standard")
    return candidates


def _promote_route_depth(candidates: list[RouteProfile]) -> list[RouteProfile]:
    deepest_route = max(candidates, key=lambda route: route.estimated_cost_usd, default=None)
    if deepest_route is None:
        return []
    remaining = [route for route in candidates if route is not deepest_route]
    return [deepest_route, *remaining]


def _load_route_profile(
    routing_payload: dict[str, object] | None,
    profile_name: str,
    default_profile: RouteProfile,
) -> RouteProfile:
    if routing_payload is None:
        return default_profile

    profile_payload = routing_payload.get(profile_name)
    if profile_payload is None:
        return default_profile
    if not isinstance(profile_payload, dict):
        raise RoutingInputError(f"guardrail config routing.{profile_name} must be an object")

    provider = profile_payload.get("provider", default_profile.provider)
    model_id = profile_payload.get("model_id", default_profile.model_id)
    estimated_cost_usd = profile_payload.get("estimated_cost_usd", default_profile.estimated_cost_usd)

    if not isinstance(provider, str) or not provider.strip():
        raise RoutingInputError(f"guardrail config routing.{profile_name}.provider must be a non-empty string")
    if not isinstance(model_id, str) or not model_id.strip():
        raise RoutingInputError(f"guardrail config routing.{profile_name}.model_id must be a non-empty string")
    if not isinstance(estimated_cost_usd, int | float):
        raise RoutingInputError(f"guardrail config routing.{profile_name}.estimated_cost_usd must be numeric")

    return RouteProfile(
        provider=provider,
        model_id=model_id,
        route_family=default_profile.route_family,
        estimated_cost_usd=float(estimated_cost_usd),
        supports_extended_tools=default_profile.supports_extended_tools,
        supports_platform_sensitive_work=default_profile.supports_platform_sensitive_work,
    )
