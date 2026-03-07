# Phase 7 Turnkey Project Build

## Purpose

This document defines the implementation contract for the first turnkey project-completion milestone after autonomous single-ticket execution. Phase 7 turns HiggsAgent into a project-building runtime that can keep working through a repository ticket graph until the application is complete or a bounded stop condition is reached.

## Goal

Phase 7 delivers the first project-completion layer for HiggsAgent:

1. orchestrate repeated autonomous ticket execution across a repository ticket graph
2. support checkpointing, resume, and bounded retry behavior for long-running project builds
3. produce reviewable commits, summaries, and handoff bundles for multi-ticket runs
4. give operators a single command to attempt a full app build under explicit safety and policy controls

The phase is successful when an operator can point HiggsAgent at a repository and run a bounded, observable, end-to-end project build workflow without manually driving each ticket.

## In Scope

- project-level orchestration over repeated single-ticket autonomous runs
- stop conditions for no-ready-ticket, blocked dependency graph, policy block, repeated failure, validation failure, or operator-configured attempt limits
- checkpoint and resume support for interrupted project runs
- project-level review bundles, summary output, and optional commit strategy
- end-to-end test fixtures for complete sample-project runs
- operator documentation for full-project autonomous build workflows and limits

## Out of Scope

- unlimited autonomous loops without stop conditions
- distributed remote worker fleets
- background SaaS control planes as a required dependency
- production deployment automation after project completion
- opaque quality scoring replacing explicit tests and review criteria

## Required Inputs

Phase 7 may rely only on stabilized earlier-phase contracts:

- autonomous single-ticket execution from [phase-6-autonomous-ticket-execution.md](phase-6-autonomous-ticket-execution.md)
- dispatcher, observability, analytics, hybrid execution, adaptive metadata, and benchmarking compatibility from Phases 1 through 5
- safety, runtime, retention, and secret-handling rules from the existing contracts under `docs/`

## Turnkey Project Build Contract

### 1. Project-Orchestration Loop

- HiggsAgent must repeatedly select and execute ready tickets until a terminal condition is reached.
- Ticket ordering must continue to respect MuonTickets dependency and workflow semantics.
- Project-level progress must remain visible through summaries, comments, and run telemetry.

### 2. Resume And Recovery

- Long-running project builds must record enough checkpoint state to resume after interruption.
- Repeated failures must be bounded and observable rather than silently retried forever.
- Operators must be able to distinguish terminal failure from resumable partial completion.

### 3. Review And Commit Strategy

- Multi-ticket runs must produce reviewable output, including changed paths, validation evidence, and ticket progression.
- If commit creation is supported, it must be explicit, bounded, and attributable to completed ticket slices or review bundles.
- Handoff bundles must make it clear which tickets completed, which were blocked, and which remain untouched.

### 4. First-Party Turnkey Operator Surface

- HiggsAgent must expose a first-party command for full-project autonomous execution.
- The command must rely on the Phase 6 single-ticket runtime instead of duplicating its logic.
- Operator inputs must make stop conditions, retry bounds, commit policy, and review behavior explicit.

### 5. Test And Benchmark Compatibility

- Full-project autonomous runs must remain observable enough for analytics and later benchmarking.
- Project-completion fixtures must make it possible to compare models or runtime policies against the same repository graph.
- End-to-end tests must verify project completion, resume behavior, blocked states, and review bundle output.

## Phase 7 Child Ticket Map

- `T-000058`: create the Phase 7 turnkey project build epic
- `T-000059`: implement project-level autonomous orchestration and resume checkpoints
- `T-000060`: implement bounded retry, stop-condition, and review-bundle behavior for full-project runs
- `T-000061`: add end-to-end project-completion coverage and benchmark fixtures
- `T-000062`: write operator and adopter documentation for turnkey project builds

## Delivery Rules

- project-level orchestration must reuse the single-ticket autonomous runtime instead of splitting the architecture
- resume and retry behavior must be explicit, bounded, and observable
- full-project execution must preserve the existing safety and review posture by default
- project-completion output must remain comparable across models and runs

## Exit Criteria

Phase 7 is complete only when:

- a first-party full-project autonomous build command exists
- HiggsAgent can progress through a repository ticket graph without manual ticket-by-ticket invocation
- interrupted runs can resume from checkpoints without losing workflow state
- tests cover successful completion, bounded failure, blocked graphs, and resume paths
- documentation explains how to run, monitor, and review a full-project autonomous build