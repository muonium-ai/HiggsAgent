# Adaptive Dispatch Development

## Audience

Contributors changing adaptive telemetry ingestion, scoring, observability, or later dispatcher integration.

## Purpose

Explain the current Phase 4 adaptive implementation boundary so contributor changes preserve the scoring contract, observability compatibility, and the separation between deterministic eligibility and adaptive ranking.

## Source Contracts

Adaptive dispatch work must stay aligned with:

- [../phase-4-adaptive-dispatch.md](../phase-4-adaptive-dispatch.md)
- [../phase-1-dispatcher-mvp.md](../phase-1-dispatcher-mvp.md)
- [../phase-2-analytics-observability.md](../phase-2-analytics-observability.md)
- [../phase-2-analytics-metric-model.md](../phase-2-analytics-metric-model.md)
- [../observability-contract.md](../observability-contract.md)
- [../runtime-tooling.md](../runtime-tooling.md)

## Current Implementation Boundary

Phase 4 currently delivers three adaptive surfaces:

- telemetry normalization in `higgs_agent.adaptive.telemetry`
- explainable scoring and selection in `higgs_agent.adaptive.scoring`
- contract and regression coverage for telemetry gaps, stale inputs, tie-breaks, and schema compatibility

Keep these distinctions clear:

- deterministic routing still decides which candidates are eligible
- adaptive scoring only ranks already-eligible candidates
- explicit execution-target rules remain hard exclusions
- stale or missing telemetry must degrade to deterministic defaults rather than silently deleting candidates
- observability compatibility is carried through metadata payloads, not by changing the attempt-summary schema

The live dispatcher path is not yet the canonical caller of adaptive selection. Do not document or imply that adaptive scoring has already replaced deterministic routing in production flow.

## Telemetry Rules

Adaptive telemetry inputs must stay normalized and reviewable.

- build snapshots only from normalized attempt summaries or analytics aggregates
- preserve explicit `telemetry_gaps` markers for unavailable or partial metrics
- distinguish precise hosted cost from local partial-usage reporting
- preserve freshness metadata and keep stale telemetry behavior deterministic
- never feed raw prompts, raw provider payloads, secret-bearing artifacts, or ad hoc provider heuristics into scoring

If a new signal cannot be represented safely in normalized telemetry, it is not ready to become a scoring input.

## Scoring And Explainability Rules

Changes to adaptive scoring must keep the policy inspectable.

- weights remain explicit and reviewable
- exclusions remain explicit and should be serializable for observability payloads
- explanations must be route-level and sufficient to explain why a candidate won or lost
- tie-break behavior must stay deterministic for the same inputs
- capability-fit logic must not smuggle provider-specific eligibility rules into the scoring layer

Treat `AdaptiveRouteSelection.as_metadata_payload()` as part of the current compatibility surface. If you change its shape, update tests and operator docs in the same change.

## Safe Change Rules

When changing adaptive behavior:

- update tests and docs in the same change
- keep deterministic routing and adaptive scoring as separate concerns
- preserve attempt-summary and execution-event schema compatibility
- preserve analytics aggregation over normalized attempt summaries
- make rollout state explicit when behavior exists as a validated surface but is not yet wired into the live dispatcher path

Require tighter review if a change:

- alters scoring weights or factor semantics
- changes stale-telemetry fallback behavior
- changes telemetry gap meanings for local usage or cost data
- wires adaptive scoring into dispatcher route choice or fallback preference
- changes the adaptive metadata payload consumed by observability tooling

## Recommended Validation

For adaptive-focused changes, run:

```bash
uv run pytest tests/Unit/test_adaptive_telemetry.py \
  tests/Unit/test_adaptive_scoring.py \
  tests/Integration/test_adaptive_dispatch_contract.py

uv run pytest tests/Unit/test_analytics_reporting.py \
  tests/Integration/test_dispatcher_pipeline.py

make tickets-validate
```

Run broader test coverage when the change touches shared schemas, provider execution results, or future dispatcher integration.

## Phase 4 Limits

Do not quietly expand Phase 4 beyond its current contract.

- no reinforcement learning or auto-tuned weights
- no required external policy service
- no benchmark fanout or same-ticket multi-provider execution mode
- no provider adapter shortcuts that bypass normalized telemetry
- no unsupported claims that adaptive scoring alone changes write-gate, fallback, or guardrail decisions

Keep Phase 4 documentation honest: the repository now has adaptive telemetry and scoring surfaces, but later work is still required before adaptive scoring becomes the default live dispatcher policy.