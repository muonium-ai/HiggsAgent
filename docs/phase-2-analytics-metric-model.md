# Phase 2 Analytics Metric Model

## Purpose

This document defines the normalized aggregate record for Phase 2 analytics work. It translates the Phase 1 attempt-summary contract into stable reporting buckets that later code and tests can implement without re-deciding how metrics are grouped or retained.

## Source of Truth

- Attempt summaries are the primary aggregation input.
- Event streams are secondary inputs used for reconciliation, drill-down, or backfill when summary-derived counts need verification.
- Raw prompts, raw provider responses, and provider-specific payload bodies are never valid analytics inputs for aggregate reporting.

## Aggregate Record

The normalized aggregate record is defined by [../schemas/analytics-aggregate.schema.json](../schemas/analytics-aggregate.schema.json).

Each record represents one aggregation bucket over a time window and optional dimension set.

### Required Record Sections

- `window`: the covered time range and bucket granularity
- `group_by`: the dimensions used to create the bucket
- `dimensions`: the concrete dimension values for that bucket
- `source`: how many normalized summaries and events contributed to the bucket
- `metrics`: derived counters, totals, averages, and error-kind rollups

## Allowed Dimensions

Phase 2 aggregates may be grouped only by dimensions already normalized elsewhere in the repo:

- `provider`
- `model`
- `ticket_type`
- `ticket_priority`
- `higgs_platform`
- `higgs_complexity`
- `final_result`
- `error_kind`

These map directly to the existing execution summary fields plus the deterministic ticket semantics contract.

## Derivation Rules

### Attempt counting

- One attempt summary contributes at most one count to `attempts_total`.
- `distinct_ticket_count` counts unique `ticket_id` values inside the bucket window.
- `succeeded_count`, `failed_count`, `blocked_count`, and `skipped_count` are derived directly from `final_result`.

### Time and latency

- `duration_ms` from the attempt summary is the authoritative duration value for aggregate totals.
- If a summary omits `duration_ms` but includes `usage.latency_ms`, the analytics pipeline may backfill the duration from that normalized latency.
- Aggregates must not inspect raw provider timings when normalized summary timing is available.

### Usage and cost

- Token totals are summed from `usage.tokens_prompt`, `usage.tokens_completion`, and `usage.total_tokens`.
- Cost totals are summed from `usage.cost_usd`.
- Average cost and average duration are computed over contributing attempts in the bucket.

### Retries and tools

- `retry_count_total` is the sum of `retry_count` across contributing attempts.
- `retried_attempt_count` counts attempts where `retry_count > 0`.
- Tool metrics derive from `tool_call_count` only; raw tool transcripts are not analytics inputs.

### Errors and failure classes

- Error-kind rollups derive from normalized `error.kind` values.
- Missing error information contributes zero to all error-kind counters.
- `error_kind` is a valid grouping dimension only for normalized values already allowed by the common error schema.

### Ticket metadata enrichment

- `ticket_type` and `ticket_priority` are sourced from MuonTickets frontmatter.
- `higgs_platform` and `higgs_complexity` are sourced from the Higgs ticket semantics contract and its normalization rules.
- Aggregates store normalized dimension values, not full ticket documents.

## Local Storage Layout

Phase 2 aggregate state remains local-only by default.

- `.higgs/local/analytics/attempt-summaries.ndjson`: normalized attempt summaries
- `.higgs/local/analytics/aggregates/<window>.ndjson`: schema-aligned aggregate records
- `.higgs/local/analytics/exports/<generated_at>.json`: sanitized export bundles derived from aggregate records

Aggregate files belong under local analytics storage even when their fields are export-safe. They move into a shareable form only through explicit export steps.

## Retention and Sharing Rules

- Local aggregate snapshots follow the same default 90-day local retention window as normalized attempt summaries unless an operator chooses a shorter retention policy.
- Export bundles may be retained longer only when they contain schema-aligned aggregate records and no raw prompt, raw response, header, env, or secret-bearing content.
- Export-safe analytics data is limited to normalized dimensions, counts, rates, totals, averages, and error-kind summaries.
- Run identifiers, attempt identifiers, raw artifact contents, and provider payload bodies remain local-only and must not appear in exported aggregate bundles.

## Implementation Boundary

- T-000023 defines the aggregate contract only.
- T-000024 implements aggregation and reporting over this contract.
- T-000025 validates the contract with broader integration coverage.
- T-000026 documents operator-facing analytics usage.