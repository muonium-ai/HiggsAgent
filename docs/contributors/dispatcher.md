# Dispatcher Development

## Audience

Contributors changing the deterministic dispatcher and its public usage guidance.

## Purpose

Explain the implemented dispatcher boundary, the current orchestration surface, and the lines contributors should not blur when extending the runtime.

## Source Contracts

Dispatcher changes must stay aligned with:

- [../phase-1-dispatcher-mvp.md](../phase-1-dispatcher-mvp.md)
- [../routing-normalization.md](../routing-normalization.md)
- [../observability-contract.md](../observability-contract.md)
- [../safety-model.md](../safety-model.md)
- [../runtime-tooling.md](../runtime-tooling.md)

## Implemented Dispatcher Boundary

The implemented dispatcher is still intentionally narrow.

- ticket eligibility lives in `higgs_agent.tickets`
- semantic normalization lives in `higgs_agent.routing.classifier`
- route selection lives in `higgs_agent.routing.policy`
- provider execution lives behind hosted and local provider adapters
- write-gate decisions live in `higgs_agent.validation`
- orchestration across those pieces lives in `higgs_agent.application.dispatch_next_ready_ticket`

Keep those surfaces separate. Do not collapse validation into provider execution or hide route policy inside provider adapters.

## Current Usage Surface

The public dispatcher surface is currently Python-first.

- analytics reporting has a CLI
- dispatcher execution does not yet have a stable end-user CLI
- the tested usage boundary is the application-layer function plus fixture-backed integration tests

When writing docs or examples, do not imply that `higgs-agent` can yet run repository dispatch end to end from a stable command-line interface.

## Configuration Assumptions

Dispatcher behavior depends on:

- `config/guardrails.example.json`
- `config/write-policy.example.json`

Contributor changes that alter dispatcher behavior should explain whether they affect:

- route eligibility
- tool-call budgets
- retry behavior
- protected-path handling
- review handoff conditions
- observability or analytics compatibility

## Safe Change Rules

When changing dispatcher behavior:

- update docs and tests in the same change
- keep the route rationale inspectable
- preserve event and attempt-summary compatibility
- keep write-gate logic independently testable
- separate implemented behavior from future adaptive or benchmarking phases

If a change needs a new operator claim, update the operator dispatcher guide at the same time.

## Minimal Example Boundary

The current orchestration entry point expects:

- a ticket directory
- a hosted transport
- optional local transport
- guardrail and write-policy paths
- a proposed change set and validation summary

That is the right abstraction level for integration tests and documentation today. Avoid introducing usage examples that skip those control-plane inputs.

## Recommended Validation

For dispatcher-focused changes, run:

```bash
uv run pytest tests/Unit/test_routing_policy.py \
  tests/Unit/test_openrouter_executor.py \
  tests/Unit/test_hybrid_provider_contract.py \
  tests/Integration/test_dispatcher_pipeline.py

make tickets-validate
```

Run broader test coverage when changes affect analytics, schemas, or repository write policy.

## Phase Separation

Keep the documentation honest about the phase boundaries.

- deterministic dispatcher behavior belongs to the Phase 1 story
- analytics reporting is Phase 2
- local execution and bounded fallback are Phase 3 extensions
- adaptive routing and benchmarking remain roadmap work

Contributors should preserve that separation in code comments, docs, tests, and review summaries.