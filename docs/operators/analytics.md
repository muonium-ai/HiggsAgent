# Analytics Operations

## Audience

Operators and reviewers working with HiggsAgent analytics outputs.

## Purpose

Explain where analytics data lives, how reports are generated, what can be shared, and what must remain local-only.

## Analytics Storage

Phase 2 analytics data lives under local-only storage by default:

- `.higgs/local/analytics/attempt-summaries.ndjson`
- `.higgs/local/analytics/aggregates/<window>.ndjson`
- `.higgs/local/analytics/exports/<generated_at>.json`

These files are execution artifacts, not committed repository state.

## Report Generation

Use the analytics CLI to render local reports from normalized attempt summaries:

```bash
uv run higgs-agent analytics report \
  --attempt-summaries .higgs/local/analytics/attempt-summaries.ndjson \
  --tickets-dir tickets \
  --group-by provider \
  --group-by ticket_type
```

Useful report options:

- `--group-by provider`
- `--group-by model`
- `--group-by ticket_type`
- `--group-by ticket_priority`
- `--group-by higgs_platform`
- `--start-at 2026-03-06T00:00:00Z`
- `--end-at 2026-03-06T23:59:59Z`
- `--format json`

## How To Read Reports

Operator-facing reports summarize normalized aggregates, not raw traces.

- `attempts`: number of contributing attempt summaries in the bucket
- `success_rate` and `failure_rate`: final-result rates for the bucket
- `cost_total_usd`: total normalized cost across contributing attempts
- `duration_avg_ms`: average normalized duration across contributing attempts
- `retries_total`: sum of attempt retry counts
- `tool_calls_total`: sum of normalized tool-call counts

Use grouped reports to compare providers, models, ticket types, or platform-specific workloads without reading provider payloads directly.

## Sharing Boundary

Only sanitized aggregate outputs are shareable by default.

Safe to share when explicitly exported and reviewed:

- normalized dimensions such as provider, model, ticket type, priority, and platform
- counts, rates, totals, and averages from aggregate records
- normalized error-kind counts
- `source.export_safe=true` aggregate outputs

Must remain local-only:

- raw prompts
- raw model responses
- provider payloads or headers
- environment values, tokens, cookies, or credential material
- attempt identifiers and run identifiers when they expose local execution traces beyond what a reviewer needs

If any input summary contains secret-bearing or raw prompt material, aggregate output should be treated as review-only and `source.export_safe` must remain `false`.

## Retention Defaults

- normalized attempt summaries: 90 days local-only
- local aggregate snapshots: 90 days local-only by default
- sanitized aggregate export bundles: longer retention only when they contain no raw or secret-bearing content

## When To Escalate

Require human review instead of sharing analytics output when:

- `source.export_safe` is `false`
- analytics content appears to include prompt or provider payload text
- secret-suspect strings appear in input artifacts or generated reports
- an operator needs data that only exists in raw traces or provider payloads

## Normative Sources

- [../phase-2-analytics-observability.md](../phase-2-analytics-observability.md)
- [../phase-2-analytics-metric-model.md](../phase-2-analytics-metric-model.md)
- [../storage-boundaries-and-retention.md](../storage-boundaries-and-retention.md)
- [../secret-handling.md](../secret-handling.md)