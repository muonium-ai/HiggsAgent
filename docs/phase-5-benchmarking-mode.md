# Phase 5 Benchmarking Mode

## Purpose

This document defines the implementation contract for the first benchmarking milestone after analytics, hybrid execution, and adaptive scoring foundations. Phase 5 introduces a reproducible comparison mode for running the same benchmark workload across multiple providers or routes without turning normal dispatch into hidden fanout.

## Goal

Phase 5 delivers the first benchmarking layer for HiggsAgent:

1. define stable benchmark workloads that represent comparable ticket shapes
2. execute those workloads across selected providers or routes under consistent control-plane settings
3. produce ranking and quality outputs from normalized benchmark results
4. keep benchmark runs reproducible, reviewable, and separate from normal repository-writing dispatch

The phase is successful when HiggsAgent can compare benchmark candidates using explicit workload manifests and normalized execution outputs, while preserving the earlier safety, observability, and analytics boundaries.

## In Scope

- benchmark workload fixtures or manifests representing comparable tasks
- multi-provider or multi-route benchmark harness execution over the same workload input
- normalized result capture for benchmark runs using existing execution contracts where possible
- ranking outputs and quality signal summaries suitable for review and comparison
- reproducibility controls for benchmark configuration, candidate set, and result interpretation
- public-facing documentation explaining methodology, limits, and safe usage

## Out of Scope

- replacing normal dispatcher routing with benchmark fanout
- hidden benchmark heuristics that directly mutate adaptive scoring weights
- external leaderboard services as a required control plane
- automatic harvesting of arbitrary repository tickets into benchmark corpora without curation
- unreviewed repository writes during comparative benchmark runs
- live production experimentation against user traffic

## Required Inputs

Phase 5 may rely only on stabilized earlier-phase contracts:

- dispatcher, provider, and validation boundaries from [phase-1-dispatcher-mvp.md](phase-1-dispatcher-mvp.md)
- analytics outputs and metric derivation rules from [phase-2-analytics-observability.md](phase-2-analytics-observability.md) and [phase-2-analytics-metric-model.md](phase-2-analytics-metric-model.md)
- hosted and local execution compatibility from [phase-3-hybrid-execution.md](phase-3-hybrid-execution.md)
- adaptive telemetry and explainability compatibility from [phase-4-adaptive-dispatch.md](phase-4-adaptive-dispatch.md)
- observability, retention, and secret-handling rules from [observability-contract.md](observability-contract.md), [storage-boundaries-and-retention.md](storage-boundaries-and-retention.md), and [secret-handling.md](secret-handling.md)
- runtime boundary rules from [runtime-tooling.md](runtime-tooling.md)

## Benchmarking Contract

### 1. Workload Corpus

- Benchmarking must run against explicit workload fixtures or manifests rather than arbitrary live ticket selection.
- Each workload should capture the ticket-shape metadata needed for comparable routing and execution, such as work type, platform, complexity, execution target assumptions, and tool profile.
- Workloads must be reusable and safe to share according to the repository's retention and redaction rules.
- Secret-bearing prompts, raw provider payloads, and ad hoc local machine state are invalid benchmark workload inputs.

### 2. Execution Harness

- Benchmarking must run the same workload across a declared candidate set of providers or routes.
- Harness execution must preserve the existing provider abstraction, event model, and attempt-summary compatibility wherever possible.
- Benchmark runs must be isolated from normal repository mutation flow; comparative execution is review-oriented, not an implicit write path.
- Benchmark mode may reuse adaptive and hybrid routing artifacts, but it must not silently bypass execution-target constraints, provider capability checks, or guardrails.

### 3. Ranking And Quality Outputs

- Benchmark outputs must expose raw comparison metrics before any composite ranking interpretation.
- Required comparison categories include success outcomes, latency, retry behavior, tool-call behavior, and cost when precise billing exists.
- Quality signals may include rubric-backed or fixture-backed evaluation outputs, but these must be explicit and reviewable rather than hidden inside provider adapters.
- Ranking outputs must make ties, missing metrics, and incomparable results visible instead of forcing opaque winner selection.

### 4. Reproducibility And Observability

- Benchmark runs must record enough metadata to reproduce the candidate set, workload selection, and scoring or ranking configuration.
- Normalized execution artifacts remain the source of truth for benchmark result derivation.
- Benchmark-specific metadata should remain compatible with later analytics and adaptive comparison work.
- Reproducibility checks should detect configuration drift, missing artifacts, or non-comparable result sets.

### 5. Safety And Runtime Boundary

- HiggsAgent remains a Python and `uv`-managed project in this phase.
- Benchmarking is an explicit mode, not the default dispatch path.
- Comparative runs must respect local-only retention boundaries for raw artifacts and must not broaden export-safe claims beyond normalized outputs.
- Public benchmark reporting must distinguish between measured outputs, inferred ranking signals, and unsupported conclusions.

## Phase 5 Child Ticket Map

- `T-000035`: implement benchmark workload manifests and fixture corpus
- `T-000036`: implement comparable multi-provider benchmark harness execution
- `T-000037`: implement benchmark ranking and quality reporting outputs
- `T-000038`: add benchmark reproducibility, contract, and regression coverage
- `T-000039`: write benchmarking methodology and public usage documentation

## Delivery Rules

- benchmarking must extend the existing observability and analytics surfaces instead of inventing a hidden side channel
- comparative runs must be explicit, reproducible, and reviewable
- benchmark outputs must distinguish measured metrics from derived quality judgments
- benchmark mode must remain separate from normal repository-writing execution flow

## Exit Criteria

Phase 5 is complete only when:

- a stable benchmark workload corpus exists for comparable provider or route evaluation
- benchmark harness execution can run the same workload across declared candidates without bypassing safety boundaries
- ranking and quality outputs explain how benchmark conclusions were derived
- tests cover reproducibility, compatibility, and failure handling for benchmark runs
- documentation explains benchmark methodology, limitations, and safe interpretation