"""Explainable adaptive route scoring over already-eligible candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from higgs_agent.adaptive.telemetry import AdaptiveTelemetryEntry, AdaptiveTelemetrySnapshot
from higgs_agent.routing import NormalizedTicketSemantics, RouteDecision


class AdaptiveScoringError(ValueError):
    """Raised when adaptive scoring inputs are invalid or unusable."""


@dataclass(frozen=True, slots=True)
class AdaptiveScoringWeights:
    """Inspectable scoring weights used by the adaptive route selector."""

    success_rate_weight: float = 0.35
    failure_rate_weight: float = 0.2
    retry_rate_weight: float = 0.1
    latency_weight: float = 0.15
    cost_weight: float = 0.1
    capability_fit_weight: float = 0.1

    def as_dict(self) -> dict[str, float]:
        return {
            "success_rate_weight": self.success_rate_weight,
            "failure_rate_weight": self.failure_rate_weight,
            "retry_rate_weight": self.retry_rate_weight,
            "latency_weight": self.latency_weight,
            "cost_weight": self.cost_weight,
            "capability_fit_weight": self.capability_fit_weight,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveCandidateExclusion:
    """Candidate excluded before scoring with an explicit reason."""

    provider: str | None
    model_id: str | None
    reason: str

    def as_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveRouteScore:
    """Score and explanation for one eligible route candidate."""

    route: RouteDecision
    total_score: float
    factor_scores: dict[str, float]
    telemetry_gaps: tuple[str, ...]
    used_deterministic_defaults: bool
    explanation: tuple[str, ...]
    tie_break_key: tuple[float, float, str, str]

    def as_payload(self, *, selected: bool) -> dict[str, object]:
        return {
            "selected": selected,
            "provider": self.route.provider,
            "model_id": self.route.model_id,
            "route_family": self.route.route_family,
            "estimated_cost_usd": self.route.estimated_cost_usd,
            "total_score": self.total_score,
            "factor_scores": dict(self.factor_scores),
            "telemetry_gaps": list(self.telemetry_gaps),
            "used_deterministic_defaults": self.used_deterministic_defaults,
            "explanation": list(self.explanation),
        }


@dataclass(frozen=True, slots=True)
class AdaptiveRouteSelection:
    """Selected route plus ranked adaptive scoring explanations."""

    selected_route: RouteDecision
    ranked_candidates: tuple[AdaptiveRouteScore, ...]
    excluded_candidates: tuple[AdaptiveCandidateExclusion, ...]
    scoring_weights: dict[str, float]
    tie_break_policy: tuple[str, ...]
    telemetry_source: str

    def as_metadata_payload(self) -> dict[str, object]:
        return {
            "selected_route": {
                "provider": self.selected_route.provider,
                "model_id": self.selected_route.model_id,
                "route_family": self.selected_route.route_family,
                "estimated_cost_usd": self.selected_route.estimated_cost_usd,
            },
            "ranked_candidates": [
                candidate.as_payload(selected=candidate.route == self.selected_route)
                for candidate in self.ranked_candidates
            ],
            "excluded_candidates": [
                candidate.as_payload() for candidate in self.excluded_candidates
            ],
            "scoring_weights": dict(self.scoring_weights),
            "tie_break_policy": list(self.tie_break_policy),
            "telemetry_source": self.telemetry_source,
        }


def select_adaptive_route(
    semantics: NormalizedTicketSemantics,
    candidates: Iterable[RouteDecision],
    telemetry_snapshot: AdaptiveTelemetrySnapshot,
    *,
    weights: AdaptiveScoringWeights | None = None,
) -> AdaptiveRouteSelection:
    """Rank already-eligible candidates and return the selected adaptive route."""

    scoring_weights = weights or AdaptiveScoringWeights()
    candidate_list = tuple(candidates)
    if not candidate_list:
        raise AdaptiveScoringError("adaptive route scoring requires at least one candidate")

    telemetry_index = {
        (entry.provider, entry.model): entry for entry in telemetry_snapshot.entries
    }
    max_known_cost = max(
        (candidate.estimated_cost_usd or 0.0 for candidate in candidate_list),
        default=0.0,
    )
    max_known_latency = max(
        (
            entry.avg_duration_ms
            for entry in telemetry_snapshot.entries
            if entry.avg_duration_ms is not None
        ),
        default=None,
    )

    scored_candidates: list[AdaptiveRouteScore] = []
    excluded_candidates: list[AdaptiveCandidateExclusion] = []
    for candidate in candidate_list:
        exclusion_reason = _candidate_exclusion_reason(semantics, candidate)
        if exclusion_reason is not None:
            excluded_candidates.append(
                AdaptiveCandidateExclusion(
                    provider=candidate.provider,
                    model_id=candidate.model_id,
                    reason=exclusion_reason,
                )
            )
            continue

        telemetry_entry = telemetry_index.get((candidate.provider or "unknown", candidate.model_id or "unknown"))
        scored_candidates.append(
            _score_candidate(
                semantics=semantics,
                candidate=candidate,
                telemetry_entry=telemetry_entry,
                weights=scoring_weights,
                max_known_cost=max_known_cost,
                max_known_latency=max_known_latency,
            )
        )

    if not scored_candidates:
        raise AdaptiveScoringError("adaptive route scoring found no eligible candidates")

    ranked_candidates = tuple(sorted(scored_candidates, key=lambda score: score.tie_break_key))
    return AdaptiveRouteSelection(
        selected_route=ranked_candidates[0].route,
        ranked_candidates=ranked_candidates,
        excluded_candidates=tuple(excluded_candidates),
        scoring_weights=scoring_weights.as_dict(),
        tie_break_policy=(
            "total_score_desc",
            "estimated_cost_usd_asc",
            "provider_asc",
            "model_id_asc",
        ),
        telemetry_source=telemetry_snapshot.source_kind,
    )


def _candidate_exclusion_reason(
    semantics: NormalizedTicketSemantics,
    candidate: RouteDecision,
) -> str | None:
    if not candidate.selected or candidate.blocked_reason is not None:
        return "candidate_not_eligible"
    if candidate.provider is None or candidate.model_id is None:
        return "candidate_missing_provider_or_model"
    if semantics.execution_target == "hosted" and candidate.provider == "local":
        return "execution_target_hosted_excludes_local"
    if semantics.execution_target == "local" and candidate.provider != "local":
        return "execution_target_local_excludes_hosted"
    return None


def _score_candidate(
    *,
    semantics: NormalizedTicketSemantics,
    candidate: RouteDecision,
    telemetry_entry: AdaptiveTelemetryEntry | None,
    weights: AdaptiveScoringWeights,
    max_known_cost: float,
    max_known_latency: float | None,
) -> AdaptiveRouteScore:
    telemetry_gaps = telemetry_entry.telemetry_gaps if telemetry_entry is not None else ("telemetry_missing",)
    used_deterministic_defaults = _should_use_deterministic_defaults(telemetry_entry)
    if used_deterministic_defaults:
        success_signal = 0.5
        failure_signal = 0.0
        retry_signal = 0.0
        latency_signal = 0.5
        cost_signal = _cost_signal(candidate, None, max_known_cost)
    else:
        success_signal = telemetry_entry.success_rate
        failure_signal = telemetry_entry.failure_rate
        retry_signal = _retry_rate(telemetry_entry)
        latency_signal = _latency_signal(telemetry_entry, max_known_latency)
        cost_signal = _cost_signal(candidate, telemetry_entry, max_known_cost)
    capability_fit = _capability_fit(candidate, semantics)

    factor_scores = {
        "success_signal": round(success_signal * weights.success_rate_weight, 6),
        "failure_penalty": round(-failure_signal * weights.failure_rate_weight, 6),
        "retry_penalty": round(-retry_signal * weights.retry_rate_weight, 6),
        "latency_signal": round(latency_signal * weights.latency_weight, 6),
        "cost_signal": round(cost_signal * weights.cost_weight, 6),
        "capability_fit": round(capability_fit * weights.capability_fit_weight, 6),
    }
    total_score = round(sum(factor_scores.values()), 6)
    explanation = _explanation(
        candidate=candidate,
        telemetry_entry=telemetry_entry,
        factor_scores=factor_scores,
        capability_fit=capability_fit,
        telemetry_gaps=telemetry_gaps,
        used_deterministic_defaults=used_deterministic_defaults,
    )
    estimated_cost = candidate.estimated_cost_usd if candidate.estimated_cost_usd is not None else 999999.0
    tie_break_key = (-total_score, estimated_cost, candidate.provider or "", candidate.model_id or "")
    return AdaptiveRouteScore(
        route=candidate,
        total_score=total_score,
        factor_scores=factor_scores,
        telemetry_gaps=telemetry_gaps,
        used_deterministic_defaults=used_deterministic_defaults,
        explanation=explanation,
        tie_break_key=tie_break_key,
    )


def _should_use_deterministic_defaults(telemetry_entry: AdaptiveTelemetryEntry | None) -> bool:
    return telemetry_entry is None or telemetry_entry.freshness_state == "stale"


def _retry_rate(telemetry_entry: AdaptiveTelemetryEntry | None) -> float:
    if telemetry_entry is None or telemetry_entry.attempts_total <= 0:
        return 0.0
    return min(telemetry_entry.retry_count_total / telemetry_entry.attempts_total, 1.0)


def _latency_signal(
    telemetry_entry: AdaptiveTelemetryEntry | None,
    max_known_latency: float | None,
) -> float:
    if telemetry_entry is None or telemetry_entry.avg_duration_ms is None:
        return 0.5
    if max_known_latency is None or max_known_latency <= 0:
        return 1.0
    return max(0.0, 1.0 - (telemetry_entry.avg_duration_ms / max_known_latency))


def _cost_signal(
    candidate: RouteDecision,
    telemetry_entry: AdaptiveTelemetryEntry | None,
    max_known_cost: float,
) -> float:
    reference_cost = telemetry_entry.avg_cost_usd if telemetry_entry and telemetry_entry.avg_cost_usd is not None else candidate.estimated_cost_usd
    if reference_cost is None:
        return 0.5
    if max_known_cost <= 0:
        return 1.0
    return max(0.0, 1.0 - (reference_cost / max_known_cost))


def _capability_fit(candidate: RouteDecision, semantics: NormalizedTicketSemantics) -> float:
    if candidate.provider == "local":
        if semantics.execution_target == "local":
            return 1.0
        if semantics.tool_profile == "none" and semantics.work_type in {"docs", "chore", "spec"}:
            return 0.9
        return 0.3

    if candidate.route_family == "deep":
        if semantics.work_type in {"code", "refactor"} or semantics.complexity == "high":
            return 1.0
        return 0.5
    if candidate.route_family == "balanced":
        if semantics.platform in {"ios", "macos"} or semantics.work_type in {"spec", "tests"}:
            return 0.95
        return 0.75
    if candidate.route_family == "economy":
        if semantics.work_type in {"docs", "chore"} and semantics.complexity != "high":
            return 1.0
        return 0.45
    return 0.5


def _explanation(
    *,
    candidate: RouteDecision,
    telemetry_entry: AdaptiveTelemetryEntry | None,
    factor_scores: dict[str, float],
    capability_fit: float,
    telemetry_gaps: tuple[str, ...],
    used_deterministic_defaults: bool,
) -> tuple[str, ...]:
    explanation = [
        f"provider:{candidate.provider}",
        f"model:{candidate.model_id}",
        f"route_family:{candidate.route_family}",
        f"capability_fit:{capability_fit:.2f}",
    ]
    if telemetry_entry is None:
        explanation.append("telemetry:missing")
    else:
        explanation.append(f"telemetry_source:{telemetry_entry.source_kind}")
        explanation.append(f"success_rate:{telemetry_entry.success_rate:.2f}")
        explanation.append(f"failure_rate:{telemetry_entry.failure_rate:.2f}")
        explanation.append(f"freshness_state:{telemetry_entry.freshness_state}")
    if telemetry_gaps:
        explanation.append(f"telemetry_gaps:{','.join(telemetry_gaps)}")
    if used_deterministic_defaults:
        explanation.append("adaptive_default:deterministic")
    explanation.extend(f"{name}:{value:.4f}" for name, value in factor_scores.items())
    return tuple(explanation)