# Phase 3 Hybrid Hosted and Local Execution

## Purpose

This document defines the implementation contract for the first hybrid execution milestone after the hosted-only dispatcher and analytics phases. Phase 3 introduces explicit local-model execution without weakening the existing provider, guardrail, observability, or review boundaries.

## Goal

Phase 3 delivers the first hybrid execution layer for HiggsAgent:

1. preserve the hosted executor contract from Phase 1
2. add a local execution path behind the same normalized provider-facing boundary
3. define fallback and selection behavior between hosted and local execution
4. keep hybrid execution observable enough for analytics and later adaptive routing

The phase is successful when HiggsAgent can choose between hosted and local execution through explicit policy rather than ad hoc branching, and when both paths emit comparable execution outputs.

## In Scope

- normalized provider abstraction that can represent hosted and local executors
- local-model executor boundary compatible with the existing execution event and attempt-summary contracts
- hybrid route selection and fallback policy for hosted versus local execution
- guardrail-aware handling of local execution requests that were blocked in Phase 1
- analytics-compatible observability for hosted and local attempts
- fixture-backed tests for hybrid selection, fallback, and failure behavior
- runtime and operator documentation for local model prerequisites and hybrid limits

## Out of Scope

- adaptive or score-based route selection
- benchmarking multiple providers against the same ticket in a single workflow
- distributed worker scheduling
- production packaging for local model runtimes
- dynamic model quality scoring
- a plugin marketplace for third-party providers

## Required Inputs

Phase 3 may rely only on stabilized earlier-phase contracts:

- hosted executor and routing boundaries from [phase-1-dispatcher-mvp.md](phase-1-dispatcher-mvp.md)
- analytics outputs and retention-safe observability from [phase-2-analytics-observability.md](phase-2-analytics-observability.md)
- aggregate metric and export-safety expectations from [phase-2-analytics-metric-model.md](phase-2-analytics-metric-model.md)
- observability rules from [observability-contract.md](observability-contract.md)
- runtime boundary rules from [runtime-tooling.md](runtime-tooling.md)
- safety and secret-handling rules from [safety-model.md](safety-model.md) and [secret-handling.md](secret-handling.md)

## Hybrid Execution Contract

### 1. Provider Abstraction

- Hosted and local executors must share a normalized execution result shape.
- Provider-specific request or response details stay behind provider adapters.
- The common abstraction must preserve timing, token or usage estimates where available, retry counts, tool-call activity, and normalized error information.

### 2. Local Execution Boundary

- Local execution must be opt-in and policy-controlled rather than an implicit fallback for every ticket.
- Local executors must emit the same event lifecycle and attempt-summary shapes used by hosted execution.
- When local runtimes cannot supply exact token or cost data, they must emit explicit partial or unavailable values instead of fabricated metrics.

### 3. Hybrid Routing and Fallback

- `higgs_execution_target=local` must become routable in Phase 3 through explicit hybrid policy.
- `higgs_execution_target=auto` may choose hosted or local execution based on deterministic rules, not adaptive scoring.
- Fallback from local to hosted or hosted to local must be explicit, bounded, and observable in event output.
- Fallback rules must not bypass existing guardrails or the write gate.

### 4. Observability and Analytics Compatibility

- Hosted and local attempts must remain comparable through shared event and summary fields.
- Hybrid execution must emit enough metadata for Phase 2 analytics to distinguish hosted versus local runs by provider and model family.
- Partial local metrics must not be mistaken for precise hosted billing data.

### 5. Runtime Boundary

- HiggsAgent remains a Python and `uv`-managed project in this phase.
- Local model support must fit within the existing runtime contract rather than introducing a second product runtime stack.
- Documentation must make local prerequisites, unsupported environments, and operational limits explicit.

## Phase 3 Child Ticket Map

- `T-000027`: define and implement the shared hybrid provider abstraction for hosted and local executors
- `T-000028`: implement hybrid route selection and bounded fallback policy
- `T-000029`: add hybrid execution contract, integration, and failure-path coverage
- `T-000030`: write hybrid runtime and operator documentation

## Delivery Rules

- Hybrid execution must extend the existing provider and observability boundaries instead of replacing them.
- Local execution must remain deterministic and testable under fixture-backed conditions.
- Event and summary output must stay compatible with Phase 2 analytics inputs.
- Any local-runtime gaps in metering or capability must be surfaced explicitly in documentation and execution metadata.

## Exit Criteria

Phase 3 is complete only when:

- hosted and local execution paths share a stable normalized abstraction
- local execution requests are no longer categorically blocked when allowed by hybrid policy
- bounded fallback behavior exists and is observable in execution records
- tests cover hybrid selection, fallback, and failure scenarios
- documentation explains how local execution is enabled, what it requires, and where the limits remain