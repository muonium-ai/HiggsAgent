from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from higgs_agent.adaptive import (
    AdaptiveScoringError,
    AdaptiveScoringWeights,
    build_adaptive_snapshot_from_attempt_summaries,
    select_adaptive_route,
)
from higgs_agent.routing import NormalizedTicketSemantics, RouteDecision


def test_adaptive_scoring_prefers_high_success_lower_cost_route() -> None:
    semantics = _semantics(execution_target="auto", work_type="docs", tool_profile="none")
    snapshot = build_adaptive_snapshot_from_attempt_summaries(
        (
            _summary("openrouter", "openai/gpt-4o-mini", "succeeded", cost_usd=0.03, duration_ms=900),
            _summary("openrouter", "openai/gpt-4o-mini", "succeeded", cost_usd=0.02, duration_ms=800),
            _summary("openrouter", "openai/gpt-4o", "failed", cost_usd=0.2, duration_ms=2000),
            _summary("openrouter", "openai/gpt-4o", "succeeded", cost_usd=0.18, duration_ms=1800),
        ),
        generated_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
    )

    selection = select_adaptive_route(
        semantics,
        (
            _candidate("openrouter", "openai/gpt-4o-mini", "economy", estimated_cost_usd=0.35),
            _candidate("openrouter", "openai/gpt-4o", "balanced", estimated_cost_usd=2.0),
        ),
        snapshot,
    )

    assert selection.selected_route.model_id == "openai/gpt-4o-mini"
    assert selection.scoring_weights["success_rate_weight"] == AdaptiveScoringWeights().success_rate_weight
    assert selection.tie_break_policy == (
        "total_score_desc",
        "estimated_cost_usd_asc",
        "provider_asc",
        "model_id_asc",
    )
    assert selection.ranked_candidates[0].total_score > selection.ranked_candidates[1].total_score
    assert "success_signal" in selection.ranked_candidates[0].factor_scores
    assert any(item.startswith("success_rate:") for item in selection.ranked_candidates[0].explanation)


def test_adaptive_scoring_preserves_execution_target_constraints() -> None:
    semantics = _semantics(execution_target="hosted", work_type="docs", tool_profile="none")
    snapshot = build_adaptive_snapshot_from_attempt_summaries(
        (_summary("local", "local/llama3.1:8b", "succeeded", duration_ms=300),),
        generated_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
    )

    selection = select_adaptive_route(
        semantics,
        (
            _candidate("local", "local/llama3.1:8b", "local", estimated_cost_usd=0.0),
            _candidate("openrouter", "openai/gpt-4o-mini", "economy", estimated_cost_usd=0.35),
        ),
        snapshot,
    )

    assert selection.selected_route.provider == "openrouter"
    assert selection.excluded_candidates == (
        type(selection.excluded_candidates[0])(
            provider="local",
            model_id="local/llama3.1:8b",
            reason="execution_target_hosted_excludes_local",
        ),
    )
    assert selection.ranked_candidates[0].telemetry_gaps == ("telemetry_missing",)


def test_adaptive_scoring_uses_tie_break_rules_deterministically() -> None:
    semantics = _semantics(execution_target="auto", work_type="docs", tool_profile="none")
    snapshot = build_adaptive_snapshot_from_attempt_summaries((), generated_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC))

    selection = select_adaptive_route(
        semantics,
        (
            _candidate("openrouter", "openai/gpt-4o", "balanced", estimated_cost_usd=2.0),
            _candidate("openrouter", "openai/gpt-4o-mini", "economy", estimated_cost_usd=0.35),
        ),
        snapshot,
        weights=AdaptiveScoringWeights(
            success_rate_weight=0.0,
            failure_rate_weight=0.0,
            retry_rate_weight=0.0,
            latency_weight=0.0,
            cost_weight=0.0,
            capability_fit_weight=0.0,
        ),
    )

    assert selection.ranked_candidates[0].route.model_id == "openai/gpt-4o-mini"
    assert selection.ranked_candidates[1].route.model_id == "openai/gpt-4o"


def test_adaptive_scoring_falls_back_to_deterministic_defaults_for_stale_telemetry() -> None:
    semantics = _semantics(execution_target="auto", work_type="docs", tool_profile="none")
    snapshot = build_adaptive_snapshot_from_attempt_summaries(
        (
            _summary("openrouter", "openai/gpt-4o", "succeeded", cost_usd=0.01, duration_ms=100),
        ),
        generated_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
        freshness_reference=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
    )
    stale_snapshot = type(snapshot)(
        source_kind=snapshot.source_kind,
        generated_at=snapshot.generated_at,
        entries=(
            replace(
                snapshot.entries[0],
                freshness_state="stale",
                telemetry_gaps=tuple(sorted((*snapshot.entries[0].telemetry_gaps, "stale_telemetry"))),
            ),
        ),
    )

    selection = select_adaptive_route(
        semantics,
        (
            _candidate("openrouter", "openai/gpt-4o", "balanced", estimated_cost_usd=2.0),
            _candidate("openrouter", "openai/gpt-4o-mini", "economy", estimated_cost_usd=0.35),
        ),
        stale_snapshot,
    )

    assert selection.selected_route.model_id == "openai/gpt-4o-mini"
    assert all(candidate.used_deterministic_defaults for candidate in selection.ranked_candidates)
    assert any(
        item == "adaptive_default:deterministic"
        for item in selection.ranked_candidates[0].explanation
    )


def test_adaptive_scoring_rejects_missing_eligible_candidates() -> None:
    semantics = _semantics(execution_target="local")
    snapshot = build_adaptive_snapshot_from_attempt_summaries((), generated_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC))

    with pytest.raises(AdaptiveScoringError, match="no eligible candidates"):
        select_adaptive_route(
            semantics,
            (_candidate("openrouter", "openai/gpt-4o", "balanced", selected=False),),
            snapshot,
        )


def _semantics(
    *,
    execution_target: str,
    work_type: str = "code",
    tool_profile: str = "standard",
    complexity: str = "medium",
    platform: str = "repo",
) -> NormalizedTicketSemantics:
    return NormalizedTicketSemantics(
        ticket_id="T-adaptive-1",
        work_type=work_type,
        priority="p1",
        platform=platform,
        complexity=complexity,
        execution_target=execution_target,
        tool_profile=tool_profile,
        labels=(),
        tags=(),
        warnings=(),
    )


def _candidate(
    provider: str,
    model_id: str,
    route_family: str,
    *,
    estimated_cost_usd: float | None = 1.0,
    selected: bool = True,
) -> RouteDecision:
    return RouteDecision(
        ticket_id="T-adaptive-1",
        priority="p1",
        selected=selected,
        provider=provider,
        model_id=model_id,
        route_family=route_family,
        estimated_cost_usd=estimated_cost_usd,
        requires_tool_calls=False,
        blocked_reason=None,
        rationale=(f"selected_model:{model_id}",),
    )


def _summary(
    provider: str,
    model: str,
    final_result: str,
    *,
    cost_usd: float | None = None,
    duration_ms: int | None = None,
) -> dict[str, object]:
    usage: dict[str, object] = {}
    if cost_usd is not None:
        usage["cost_usd"] = cost_usd
    if duration_ms is not None:
        usage["latency_ms"] = duration_ms
    return {
        "ticket_id": "T-adaptive-1",
        "provider": provider,
        "model": model,
        "final_result": final_result,
        "retry_count": 0,
        "tool_call_count": 0,
        "ended_at": "2026-03-07T11:00:00Z",
        "usage": usage,
    }