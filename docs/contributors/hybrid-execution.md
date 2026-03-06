# Hybrid Execution Development

## Audience

Contributors changing hosted versus local execution behavior in HiggsAgent.

## Purpose

Explain the current Phase 3 hybrid execution implementation boundary so contributor changes stay aligned with the routing, runtime, observability, and analytics contracts.

## Source Contracts

Hybrid execution work must stay aligned with:

- [../phase-3-hybrid-execution.md](../phase-3-hybrid-execution.md)
- [../runtime-tooling.md](../runtime-tooling.md)
- [../observability-contract.md](../observability-contract.md)
- [../phase-2-analytics-observability.md](../phase-2-analytics-observability.md)
- [../phase-2-analytics-metric-model.md](../phase-2-analytics-metric-model.md)

## Current Implementation Boundary

Phase 3 is intentionally narrow.

- hosted and local executors share the same normalized result contract
- local execution remains behind a provider adapter boundary
- route selection is deterministic rather than score-based
- bounded fallback currently applies only from failed auto-local attempts to hosted execution
- explicit local requests remain explicit and do not silently switch providers

Contributors should treat those rules as part of the current public behavior, not incidental implementation detail.

## Local Runtime Expectations

Do not assume the repository owns local runtime installation.

- local runtimes are external prerequisites, not project-managed dependencies
- HiggsAgent remains Python-plus-`uv`; do not add a second product runtime stack
- local transports may return partial usage information, especially around exact billing
- tool-enabled local execution is still out of scope in this phase

## Safe Change Rules

When changing hybrid behavior:

- update routing policy, dispatcher behavior, docs, and tests in the same change
- preserve event and attempt-summary schema compatibility
- keep fallback decisions inspectable through rationale, events, or execution metadata
- make unavailable local metrics explicit instead of fabricating hosted-style values
- avoid widening local support claims beyond what the runtime docs actually define

## Recommended Validation

Use the hybrid-focused validation stack when changing provider, routing, or fallback behavior:

```bash
uv run pytest tests/Unit/test_hybrid_provider_contract.py \
  tests/Unit/test_routing_policy.py \
  tests/Unit/test_openrouter_executor.py \
  tests/Integration/test_dispatcher_pipeline.py

uv run pytest tests/Unit/test_analytics_reporting.py \
  tests/Integration/test_analytics_reporting_pipeline.py
```

Run broader validation when the change touches shared schemas, CLI behavior, or storage boundaries.

## Review Triggers

Require tighter review when a change:

- alters deterministic selection rules for `auto` or `local`
- wires adaptive scoring into the live dispatcher path or fallback selection flow
- changes fallback direction or broadens fallback eligibility
- changes the meaning of local partial-usage reporting
- changes operator claims around supported local environments
- introduces runtime discovery, packaging, or external daemon assumptions