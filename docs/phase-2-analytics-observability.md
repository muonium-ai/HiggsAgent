# Phase 2 Analytics and Observability

## Purpose

This document defines the implementation contract for the first analytics milestone after the deterministic dispatcher MVP. Phase 2 turns the Phase 1 event stream and attempt summaries into usable reporting surfaces without taking over execution control.

## Goal

Phase 2 delivers the first operator-facing analytics layer for HiggsAgent:

1. ingest schema-compliant attempt summaries and event streams
2. derive stable metrics for cost, latency, retries, failure classes, and model usage
3. export local reports and aggregates for operators and future analytics consumers
4. preserve the open-source retention and redaction boundaries established in Phase 0

The phase is successful when operators can answer basic usage and performance questions from normalized analytics outputs rather than raw execution traces.

## In Scope

- local aggregation of execution attempt summaries
- metric derivation for cost, latency, success rate, retry rate, and tool-call frequency
- grouped reporting by model, provider, ticket type, and time window
- sanitized analytics exports suitable for sharing or longer retention
- operator-facing documentation for reading analytics outputs and interpreting limits
- contract and integration tests for analytics correctness and retention boundaries

## Out of Scope

- adaptive routing or score feedback into dispatch policy
- dashboard UI implementation
- hosted analytics services or external telemetry backends
- long-term warehouse design
- local-model routing changes
- benchmarking comparisons across multiple runs of the same ticket

## Required Inputs

Phase 2 may rely only on the stabilized Phase 0 and Phase 1 surfaces:

- event envelopes and attempt summaries from [observability-contract.md](observability-contract.md)
- local-only retention boundaries from [storage-boundaries-and-retention.md](storage-boundaries-and-retention.md)
- Phase 1 routing, executor, and write-gate outputs from [phase-1-dispatcher-mvp.md](phase-1-dispatcher-mvp.md)
- review and secret-handling rules from [safety-model.md](safety-model.md) and [secret-handling.md](secret-handling.md)

## Analytics Contract

### 1. Input Sources

- attempt summaries are the primary analytics source of truth
- full event streams remain available for drill-down and verification
- raw prompts, raw responses, and provider payloads stay local-only and are never required for basic aggregate reports

### 2. Core Metrics

Phase 2 should expose at minimum:

- total and average cost by provider and model
- total and average latency by provider and model
- success, failure, blocked, and skipped rates
- retry counts and failure-class counts
- tool-call frequency and average tool-call count
- volume breakdowns by ticket type, priority, and platform

### 3. Reporting Shape

- reports must be derivable from local normalized data without hidden joins to provider-specific payloads
- aggregate outputs should support filtering by time window, model, provider, and ticket shape
- summaries should be explainable to operators and safe to persist longer than raw traces when sanitized

### 4. Retention and Redaction

- raw traces remain local-only and short-lived
- normalized attempt summaries may be retained longer locally
- exported aggregates must exclude raw prompt and response content
- any metric derived from secret-bearing content is invalid and must trigger review instead of export

## Phase 2 Child Ticket Map

- `T-000023`: define analytics metric model and local aggregate storage in [phase-2-analytics-metric-model.md](phase-2-analytics-metric-model.md) and [../schemas/analytics-aggregate.schema.json](../schemas/analytics-aggregate.schema.json)
- `T-000024`: implement analytics reporting and operator query surface
- `T-000025`: add analytics contract and integration coverage
- `T-000026`: write analytics operator and contributor documentation

## Delivery Rules

- analytics outputs must not become a hidden control plane for routing in this phase
- exported summaries must stay derived from normalized schema-aligned records
- local analytics state belongs under the existing local-only storage boundary, not committed project paths
- operator-facing output must be understandable without reading raw provider payloads

## Exit Criteria

Phase 2 is complete only when:

- normalized analytics aggregates exist for the required metric categories
- reporting surfaces can answer basic operator questions about cost, latency, retries, failures, and model use
- tests cover both correctness and retention boundary expectations
- documentation explains where analytics data lives, what can be shared, and what remains local-only