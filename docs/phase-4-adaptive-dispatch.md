# Phase 4 Adaptive Dispatch

## Purpose

This document defines the implementation contract for the first adaptive dispatch milestone after deterministic hosted routing, analytics aggregation, and hybrid hosted or local execution. Phase 4 adds telemetry-backed route scoring without weakening the existing provider, guardrail, observability, or review boundaries.

## Goal

Phase 4 delivers the first adaptive routing layer for HiggsAgent:

1. ingest stable telemetry from normalized execution and analytics outputs
2. score eligible provider candidates using explicit weighted signals
3. choose routes adaptively while preserving explainability and guardrail enforcement
4. keep the scoring surface observable enough for review, regression testing, and later benchmarking work

The phase is successful when HiggsAgent can choose between eligible routes using explainable telemetry-backed scoring rather than fixed heuristics alone, while still producing reviewable execution records and stable downstream analytics inputs.

## In Scope

- telemetry-backed candidate scoring over hosted and local execution routes
- normalized signal ingestion from analytics aggregates and execution summaries
- adaptive route selection policy with explicit weights, tie-break rules, and confidence surfaces
- explainable route selection metadata suitable for observability and operator review
- fixture-backed tests for score derivation, policy selection, regressions, and failure handling
- operator and contributor documentation for adaptive scoring behavior and limits

## Out of Scope

- reinforcement learning or online self-modifying scoring weights
- hidden provider-specific heuristics that bypass the normalized scoring model
- benchmarking multiple providers against the same ticket in the live dispatch path
- automatic local runtime installation or infrastructure orchestration
- external telemetry services as a required control plane
- opaque ranking outputs without route-level explanation

## Required Inputs

Phase 4 may rely only on stabilized earlier-phase contracts:

- deterministic routing and dispatcher boundaries from [phase-1-dispatcher-mvp.md](phase-1-dispatcher-mvp.md)
- analytics outputs and derivation rules from [phase-2-analytics-observability.md](phase-2-analytics-observability.md) and [phase-2-analytics-metric-model.md](phase-2-analytics-metric-model.md)
- hybrid provider behavior from [phase-3-hybrid-execution.md](phase-3-hybrid-execution.md)
- observability rules from [observability-contract.md](observability-contract.md)
- runtime boundary rules from [runtime-tooling.md](runtime-tooling.md)
- safety and secret-handling rules from [safety-model.md](safety-model.md) and [secret-handling.md](secret-handling.md)

## Adaptive Dispatch Contract

### 1. Telemetry Inputs

- Adaptive scoring must consume only normalized telemetry inputs.
- Attempt summaries and aggregate analytics records are the primary telemetry surfaces.
- Raw prompts, raw provider payloads, and secret-bearing artifacts are never valid scoring inputs.
- Signal ingestion must distinguish between precise metrics and partial or unavailable values, especially for local cost data.

### 2. Scoring Model

- Candidate routes must be scored using explicit weighted signals rather than hidden branching logic.
- Signal categories may include latency, success or failure history, retry rate, tool support fit, cost pressure, and ticket-shape compatibility.
- Weights, normalization rules, and tie-break ordering must be configuration-backed or otherwise inspectable.
- Missing telemetry must degrade gracefully to deterministic defaults rather than causing silent route exclusion.

### 3. Selection and Safety

- Adaptive scoring may reorder eligible routes but must not bypass route eligibility, provider capability checks, guardrails, or the write gate.
- Blocked routes remain blocked even if their score would otherwise be high.
- Adaptive route selection must preserve explicit operator intent in `higgs_execution_target`.
- Fallback behavior from Phase 3 remains bounded and observable; adaptive scoring may inform fallback candidate preference but must not create unbounded retry loops.

### 4. Explainability and Observability

- Route selection output must remain explainable to operators and contributors.
- Execution records must surface enough metadata to reconstruct why the selected route outranked the alternatives.
- Observability should capture candidate score summaries, selected-signal rationale, and any telemetry gaps that affected the decision.
- Adaptive scoring outputs must remain compatible with later analytics and benchmarking work.

### 5. Runtime and Control Plane Boundary

- HiggsAgent remains a Python and `uv`-managed project in this phase.
- Adaptive scoring configuration must live within the existing repository control plane rather than requiring a hosted policy service.
- The phase may add scoring configuration or local telemetry cache inputs, but these must remain explicit repository or local-only artifacts.
- Operators must be able to review or disable adaptive behavior without editing provider adapter internals.

## Phase 4 Child Ticket Map

- `T-000031`: implement telemetry ingestion and normalized adaptive scoring inputs
- `T-000032`: implement adaptive route scoring policy and explainable selection output
- `T-000033`: add adaptive dispatch contract, regression, and failure-path coverage
- `T-000034`: write adaptive dispatch operator and contributor documentation

## Delivery Rules

- Adaptive dispatch must extend the existing routing and observability boundaries instead of replacing them.
- Score derivation must be deterministic for the same telemetry snapshot and configuration inputs.
- Telemetry gaps must be explicit in scoring output rather than hidden behind provider-specific assumptions.
- Route selection explanation must be good enough to support code review, incident review, and later benchmark comparison.

## Exit Criteria

Phase 4 is complete only when:

- normalized telemetry can be turned into stable route scores
- adaptive selection can choose among eligible routes without bypassing guardrails or write policy
- observability output explains selected versus non-selected routes well enough for review
- tests cover score derivation, adaptive selection, regressions, and failure handling
- documentation explains how adaptive behavior is configured, interpreted, and limited