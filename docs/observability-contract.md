# Observability Contract

## Purpose

HiggsAgent records execution as an append-only event stream plus a derived attempt summary. This gives Phase 1 a stable executor contract and gives later analytics work a normalized input format.

## Model

- One execution run may contain one or more attempts.
- Each attempt emits an ordered event stream.
- Each attempt also produces one normalized summary record.
- Raw provider payloads and raw prompts are not embedded directly into summary records.

## Required Event Envelope

Each event must include:

- `schema_version`
- `event_id`
- `event_type`
- `occurred_at`
- `sequence`
- `run_id`
- `attempt_id`
- `ticket_id`
- `status`

Optional but common fields include:

- `executor_version`
- `repo_head`
- `artifact_refs`
- `usage`
- `limits`
- `error`
- `payload`

## Core Lifecycle Events

- `execution.created`
- `ticket.eligibility_evaluated`
- `classification.completed`
- `route.selected`
- `guardrails.checked`
- `provider.requested`
- `tool.call.started`
- `tool.call.completed`
- `provider.responded`
- `validation.completed`
- `write_gate.decided`
- `artifact.recorded`
- `retry.scheduled`
- `execution.completed`

## Required Behavioral Rules

- Event streams are append-only.
- `execution.completed` must be emitted exactly once per attempt.
- Failures should be represented both on the failing event and on the terminal attempt summary.
- Tool and provider artifacts should be referenced by path and hash rather than duplicated inline.

## Attempt Summary

The derived attempt summary is the stable analytics-facing record and should include:

- timing
- final result
- provider and model identifiers
- total usage and cost
- tool-call count
- retry count
- artifact references
- normalized error information

## Open-Source Default

Observability is enabled, but raw payloads remain local by default. The committed repository should contain contracts, validated outputs, and optionally sanitized summaries, not raw execution traces.