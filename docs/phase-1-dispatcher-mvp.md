# Phase 1 Deterministic Dispatcher MVP

## Purpose

This document defines the implementation contract for the first dispatcher milestone. It bounds what Phase 1 must deliver, what it must leave out, and how the downstream scanner, classifier, routing, executor, validation, test, and documentation tickets fit together.

For operator-facing and contributor-facing usage guidance built on top of this contract, see [operators/dispatcher.md](operators/dispatcher.md) and [contributors/dispatcher.md](contributors/dispatcher.md).

## Goal

Phase 1 delivers the first end-to-end deterministic dispatch pipeline for HiggsAgent:

1. discover ready tickets
2. normalize approved ticket semantics
3. choose a hosted execution route deterministically
4. execute through a constrained provider boundary
5. validate the result before any repository mutation
6. emit observable execution events and attempt summaries

The MVP is successful when the pipeline is testable without hidden routing decisions or implicit write behavior.

## In Scope

- ticket discovery from the repository ticket tree
- ready-state and dependency eligibility checks
- semantic normalization using the approved Higgs fields
- deterministic hosted routing for Phase 1 ticket types
- provider execution through OpenRouter-facing interfaces
- constrained tool-call handling that respects guardrails
- output validation and explicit write or handoff decisions
- event emission compatible with the execution-event and execution-attempt schemas
- fixture-backed unit and integration tests for the implemented surfaces

## Out of Scope

- adaptive or scoring-based routing
- local model execution
- benchmarking mode
- background worker orchestration
- autonomous pushes, merges, tags, or releases
- dashboard or analytics UI work
- long-lived queue leasing beyond the existing ticket workflow

## Required Inputs

Phase 1 may rely only on approved Phase 0 contracts:

- ticket workflow fields and Higgs semantic fields from [ticket-semantics.md](ticket-semantics.md)
- normalization rules from [routing-normalization.md](routing-normalization.md)
- safety and mutation rules from [safety-model.md](safety-model.md)
- event payload rules from [observability-contract.md](observability-contract.md)
- repository ownership boundaries from [repository-structure.md](repository-structure.md)

## Pipeline Contract

### 1. Scanner Boundary

- Input: repository ticket paths and parsed ticket records
- Output: deterministic candidate set limited to valid `ready` tickets
- Must reject blocked, invalid, or non-routable tickets without invoking routing or execution
- Selection order for ready candidates is workflow-only: priority first, then ticket id for stable tie-breaking

### 2. Classifier Boundary

- Input: a validated ticket record
- Output: normalized dispatch semantics
- Must use only approved Higgs and MuonTickets fields
- Must produce explicit failures or warnings for unsupported values and missing required inputs
- Output shape must include `type`, `priority`, `platform`, `complexity`, `execution_target`, and `tool_profile` in normalized form

### 3. Routing Boundary

- Input: normalized semantics and guardrail-aware execution constraints
- Output: explainable hosted route selection
- Must remain deterministic for the same normalized input set
- Must not silently convert `local` execution requests into hosted execution
- Output must expose selected provider, model id, route family, estimated cost band, and rationale strings suitable for later event logging

### 4. Executor Boundary

- Input: selected route, validated prompt inputs, and guardrail limits
- Output: structured provider response plus execution metadata
- Must capture timing, token, cost, retry, and tool-call data needed by the observability schemas
- Must keep provider-specific behavior behind the hosted adapter boundary
- Tool-call handling must stay explicit: disabled tools hard-fail, tool-call counts are budgeted, and provider-emitted tool requests are surfaced as first-class event records

### 5. Validation Boundary

- Input: executor output, proposed repository mutations, and write policy
- Output: one of `accepted`, `handoff_required`, or `rejected`
- Must separate validation logic from provider execution so the write gate is independently testable
- Handoff decisions must include enough structured context for a human reviewer to understand changed paths, validation summary, guardrail usage, and the blocking reason without reading raw provider payloads

### 6. Event Boundary

- Input: lifecycle state transitions across scan, classify, route, execute, and validate
- Output: schema-compliant execution events and attempt summaries
- Must support white-box reasoning for later analytics without requiring later-phase features now

## Phase 1 Child Ticket Map

- `T-000011`: scanner and ready-ticket selection
- `T-000012`: semantic classifier
- `T-000013`: deterministic routing policy
- `T-000014`: OpenRouter executor and tool-call boundary
- `T-000015`: output validation and repository write gate
- `T-000016`: unit and integration coverage for the implemented boundaries
- `T-000017`: public-facing Phase 1 architecture and usage docs after interfaces stabilize

## Delivery Rules

- Phase 1 code must live under the package boundaries defined in [repository-structure.md](repository-structure.md).
- Product runtime behavior must be executable through `uv` and covered by the existing CI strategy in [testing-strategy.md](testing-strategy.md).
- Shared hotspots such as routing, provider contracts, validation, and event emission remain tightly owned and should not be spread across unrelated tickets.
- The MVP must prefer explicit handoff over unsafe autonomous repository mutation.

## Exit Criteria

Phase 1 is complete only when:

- the scanner, classifier, router, executor, and validation boundaries all exist as separate testable surfaces
- the deterministic pipeline can be exercised with fixture-backed integration coverage
- observability output is emitted in the agreed schema shapes
- the implementation remains clearly separated from later adaptive, hybrid, and benchmarking phases