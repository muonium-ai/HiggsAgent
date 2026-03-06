from __future__ import annotations

from pathlib import Path

import pytest

from higgs_agent.routing import choose_route, classify_ticket, load_route_guardrails


def test_docs_ticket_prefers_economy_route() -> None:
    semantics = classify_ticket(
        {
            "id": "T-200001",
            "type": "docs",
            "priority": "p1",
            "effort": "s",
            "higgs_schema_version": 1,
            "higgs_platform": "agnostic",
        }
    )

    decision = choose_route(
        semantics,
        load_route_guardrails(Path("config/guardrails.example.json")),
    )

    assert decision.selected is True
    assert decision.provider == "openrouter"
    assert decision.model_id == "openai/gpt-4o-mini"
    assert decision.route_family == "economy"
    assert "work_type_bias:economy_docs_route" in decision.rationale
    assert "hybrid_policy:auto_hosted_local_unavailable" in decision.rationale


def test_ios_ticket_prefers_openai_platform_sensitive_route() -> None:
    semantics = classify_ticket(
        {
            "id": "T-200002",
            "type": "code",
            "priority": "p0",
            "effort": "m",
            "higgs_schema_version": 1,
            "higgs_platform": "ios",
            "higgs_tool_profile": "standard",
        }
    )

    decision = choose_route(
        semantics,
        load_route_guardrails(Path("config/guardrails.example.json")),
    )

    assert decision.selected is True
    assert decision.model_id == "openai/gpt-4o"
    assert "platform_bias:openai_platform_sensitive" in decision.rationale


def test_code_route_falls_back_when_budget_disallows_deep_model() -> None:
    semantics = classify_ticket(
        {
            "id": "T-200003",
            "type": "code",
            "priority": "p1",
            "effort": "m",
            "higgs_schema_version": 1,
            "higgs_platform": "repo",
        }
    )

    decision = choose_route(
        semantics,
        load_route_guardrails(Path("tests/Fixtures/config/guardrails_low_budget.json")),
    )

    assert decision.selected is True
    assert decision.model_id == "openai/gpt-4o"
    assert "budget_fallback:anthropic/claude-3.5-sonnet->openai/gpt-4o" in decision.rationale


def test_explicit_local_route_selects_local_provider_when_enabled() -> None:
    semantics = classify_ticket(
        {
            "id": "T-200004",
            "type": "refactor",
            "priority": "p0",
            "effort": "l",
            "higgs_schema_version": 1,
            "higgs_platform": "repo",
            "higgs_execution_target": "local",
            "higgs_tool_profile": "none",
        }
    )

    decision = choose_route(
        semantics,
        load_route_guardrails(Path("config/guardrails.example.json")),
        local_execution_enabled=True,
    )

    assert decision.selected is True
    assert decision.provider == "local"
    assert decision.model_id == "local/llama3.1:8b"
    assert "hybrid_policy:explicit_local_route" in decision.rationale


def test_explicit_local_route_blocks_when_local_runtime_is_unavailable() -> None:
    semantics = classify_ticket(
        {
            "id": "T-200004b",
            "type": "refactor",
            "priority": "p0",
            "effort": "l",
            "higgs_schema_version": 1,
            "higgs_platform": "repo",
            "higgs_execution_target": "local",
            "higgs_tool_profile": "none",
        }
    )

    decision = choose_route(
        semantics,
        load_route_guardrails(Path("config/guardrails.example.json")),
    )

    assert decision.selected is False
    assert decision.blocked_reason == "local_execution_not_configured"
    assert "blocked:local_runtime_unavailable" in decision.rationale


def test_auto_route_prefers_local_for_low_risk_ticket_when_enabled() -> None:
    semantics = classify_ticket(
        {
            "id": "T-200004c",
            "type": "docs",
            "priority": "p1",
            "effort": "s",
            "higgs_schema_version": 1,
            "higgs_platform": "agnostic",
            "higgs_execution_target": "auto",
            "higgs_tool_profile": "none",
        }
    )

    decision = choose_route(
        semantics,
        load_route_guardrails(Path("config/guardrails.example.json")),
        local_execution_enabled=True,
    )

    assert decision.selected is True
    assert decision.provider == "local"
    assert "hybrid_policy:auto_prefers_local" in decision.rationale


def test_explicit_local_route_blocks_when_tools_are_required() -> None:
    semantics = classify_ticket(
        {
            "id": "T-200004d",
            "type": "refactor",
            "priority": "p0",
            "effort": "l",
            "higgs_schema_version": 1,
            "higgs_platform": "repo",
            "higgs_execution_target": "local",
            "higgs_tool_profile": "standard",
        }
    )

    decision = choose_route(
        semantics,
        load_route_guardrails(Path("config/guardrails.example.json")),
        local_execution_enabled=True,
    )

    assert decision.selected is False
    assert decision.blocked_reason == "local_execution_requires_toolless_route"
    assert "blocked:local_route_requires_toolless_request" in decision.rationale


def test_router_blocks_when_no_route_fits_budget() -> None:
    semantics = classify_ticket(
        {
            "id": "T-200005",
            "type": "tests",
            "priority": "p1",
            "effort": "m",
            "higgs_schema_version": 1,
            "higgs_platform": "agnostic",
            "higgs_tool_profile": "extended",
        }
    )

    decision = choose_route(
        semantics,
        load_route_guardrails(Path("tests/Fixtures/config/guardrails_tiny_budget.json")),
    )

    assert decision.selected is False
    assert decision.blocked_reason == "no_route_within_cost_ceiling"
    assert "blocked:budget_exceeded_for_all_routes" in decision.rationale


def test_guardrail_loader_rejects_missing_limits() -> None:
    with pytest.raises(ValueError, match="limits"):
        load_route_guardrails(Path("tests/Fixtures/config/guardrails_invalid_missing_limits.json"))