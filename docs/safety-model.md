# Safety Model

## Purpose

This document defines the initial guardrail model for HiggsAgent. It is the policy layer that later dispatcher, executor, and write-gate code must enforce.

## Guardrail Categories

HiggsAgent uses seven guardrail categories.

1. Token budget
2. Cost budget
3. Timeout budget
4. Tool-call budget
5. Retry budget
6. Repository mutation budget
7. Artifact retention budget

## Starter Defaults

These are conservative defaults for early implementation and testing:

- max prompt tokens: 16000
- max completion tokens: 8000
- max total tokens per ticket: 24000
- max cost per ticket: 5.00 USD
- max tool calls per ticket: 8
- provider request timeout: 120000 ms
- end-to-end ticket timeout: 900000 ms
- max attempts per ticket: 3

These defaults are configuration values, not hard-coded product promises.

## Write Policy

- Execution starts in read-only mode until the validation gate passes.
- Repository writes are allowed only inside explicitly allowed paths.
- Direct pushes, merges, tags, and releases are human-only actions.
- Autonomous commits are disabled by default in early phases.
- Raw prompts, raw responses, provider payloads, and local execution traces must never be committed by default.

## Autonomous Session Controls

Phase 6 autonomous coding introduces additional policy controls:

- autonomous execution must be explicitly enabled
- session step count must be bounded per ticket attempt
- allowed command classes must be explicit and reviewable
- validation commands must be configured rather than improvised
- scaffold creation and patch application formats must be explicitly allowed
- automatic claim, comment, and `needs_review` transitions must be operator-controlled
- local commit creation remains opt-in and disabled by default

Autonomous coding does not weaken the existing write policy. It only automates bounded repository mutation under the same review-oriented controls.

## Review Handoff Rules

Human review is mandatory when any of the following are true:

- a protected path is touched
- a soft threshold is exceeded
- the diff is non-deterministic or unclear
- validation fails after retries
- a shared hotspot is modified
- a secret risk is detected

## Failure Classes

- transient
- validation
- policy
- secret-suspect
- coordination
- materialization
- workflow

Transient failures may retry. Policy and secret-suspect failures are hard stops.

## Swarm Safety

- Shared schemas, routing rules, executor boundaries, and write-gate logic are protected surfaces.
- Workers may prepare diffs, but shared-surface write-through should remain coordinator-controlled.
- Conflicting or contested swarm changes should be handed off rather than retried blindly.