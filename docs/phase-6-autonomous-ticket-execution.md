# Phase 6 Autonomous Ticket Execution

## Purpose

This document defines the implementation contract for the first autonomous coding milestone after benchmarking mode. Phase 6 turns HiggsAgent from an explicit review-mode dispatcher into a controlled single-ticket coding runtime that can call OpenRouter, produce repository edits, run validation, and update ticket workflow state for one ready ticket at a time.

## Goal

Phase 6 delivers the first autonomous coding layer for HiggsAgent:

1. define a stable coding-session contract for tool-driven OpenRouter execution
2. let HiggsAgent infer and validate repository mutations for a single claimed or ready ticket
3. automate the single-ticket review loop including validation evidence and ticket lifecycle updates
4. preserve the existing safety, observability, and analytics boundaries while adding real repository-writing capability

The phase is successful when an operator can invoke a first-party HiggsAgent command against a repository and have HiggsAgent autonomously complete one ticket through coding, validation, and review-ready output without relying on an outer coding agent.

## In Scope

- a normalized coding-session contract for OpenRouter-backed autonomous execution
- tool-call or action-loop integration that can read files, propose edits, run tests, and record outputs
- changed-file inference from actual edits rather than operator-supplied placeholders
- validation command execution and normalized validation-summary capture
- automated ticket claim, comment, and `needs_review` transition for successful single-ticket runs
- review-handoff bundle generation for blocked or partially successful runs
- end-to-end tests for successful, blocked, and failed autonomous single-ticket execution
- operator and adopter documentation for the autonomous single-ticket flow

## Out of Scope

- completing an entire ticket graph in one invocation
- distributed multi-agent coordination
- hidden background writes without review visibility
- non-OpenRouter provider expansion beyond what the normalized boundary already supports
- production deployment or hosted control planes for autonomous execution

## Required Inputs

Phase 6 may rely only on stabilized earlier-phase contracts:

- dispatcher, provider, and validation boundaries from [phase-1-dispatcher-mvp.md](phase-1-dispatcher-mvp.md)
- autonomous coding-session normalization from [autonomous-coding-session-contract.md](autonomous-coding-session-contract.md)
- analytics and observability compatibility from [phase-2-analytics-observability.md](phase-2-analytics-observability.md) and [observability-contract.md](observability-contract.md)
- hybrid execution boundaries from [phase-3-hybrid-execution.md](phase-3-hybrid-execution.md)
- adaptive and benchmarking metadata compatibility from [phase-4-adaptive-dispatch.md](phase-4-adaptive-dispatch.md) and [phase-5-benchmarking-mode.md](phase-5-benchmarking-mode.md)
- runtime, safety, secret-handling, and storage rules from [runtime-tooling.md](runtime-tooling.md), [safety-model.md](safety-model.md), [secret-handling.md](secret-handling.md), and [storage-boundaries-and-retention.md](storage-boundaries-and-retention.md)

## Autonomous Ticket Execution Contract

### 1. Coding Session Boundary

- HiggsAgent must have a normalized coding-session abstraction distinct from the plain text completion path.
- The coding-session abstraction must represent prompts, tool or action calls, file reads, file writes, command execution, and normalized failure output.
- Repository mutations must remain inspectable through execution events and artifact references rather than hidden inside provider-specific payloads.
- The detailed action and workflow rules are defined in [autonomous-coding-session-contract.md](autonomous-coding-session-contract.md).

### 2. Workspace Mutation And Validation

- HiggsAgent must derive proposed file changes from observed workspace edits instead of relying on manually supplied changed-file arguments.
- The autonomous runtime must support configured validation commands and capture their output as normalized evidence.
- Validation failures must remain visible to the write gate and must not be rewritten into false success states.

### 3. Ticket Workflow Automation

- Successful autonomous single-ticket runs must be able to claim a ready ticket, add progress commentary, and move it to `needs_review`.
- Failed or blocked runs must record actionable failure or handoff information without corrupting ticket state.
- Ticket lifecycle automation must continue to flow through MuonTickets instead of direct frontmatter mutation.

### 4. Safety And Review Controls

- Autonomous execution must respect protected-path, secret-suspect, and review-required policies.
- Repository writes must remain review-oriented by default, with explicit operator control over whether local commits are created.
- The runtime must emit enough telemetry to reconstruct what was attempted, what changed, what validation ran, and why the write gate accepted or blocked the result.

### 5. First-Party Operator Surface

- HiggsAgent must expose a first-party command for autonomous single-ticket execution.
- The operator surface must require explicit repository-root and policy inputs, but it must not require the operator to hand-author the changed-file set or validation summary.
- The command must produce review-friendly output and concrete `.higgs/local` telemetry artifacts.

## Phase 6 Child Ticket Map

- `T-000053`: create the Phase 6 autonomous ticket execution epic
- `T-000054`: define the autonomous coding session contract and policy extensions
- `T-000055`: implement the OpenRouter-backed autonomous single-ticket execution loop
- `T-000056`: add autonomous single-ticket integration, regression, and failure-path coverage
- `T-000057`: write operator and adopter documentation for autonomous single-ticket execution
- `T-000063`: implement scaffold materialization from autonomous coding responses
- `T-000064`: implement patch and diff application for iterative autonomous edits
- `T-000065`: add fixture-backed coverage for scaffold and diff materialization
- `T-000066`: document supported autonomous response materialization formats

## Delivery Rules

- autonomous execution must extend the existing dispatcher and validation boundaries rather than bypass them
- inferred change detection and validation evidence must be explicit and inspectable
- ticket workflow automation must continue to use MuonTickets as the workflow source of truth
- operator defaults must remain safe for review-mode repository mutation

## Exit Criteria

Phase 6 is complete only when:

- a first-party autonomous single-ticket command exists
- HiggsAgent can call OpenRouter, edit repository files, run validation, and infer the actual changed-file set for one ticket
- ticket lifecycle updates are automated for success and review handoff is automated for blocked runs
- tests cover success, validation failure, policy block, and provider failure cases
- documentation explains how to run, observe, and review autonomous single-ticket execution