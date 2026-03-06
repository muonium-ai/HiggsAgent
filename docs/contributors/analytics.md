# Analytics Development

## Audience

Contributors extending HiggsAgent analytics metrics, storage, or reports.

## Purpose

Explain the contributor surface for analytics work so extensions stay compatible with the Phase 2 contracts.

## Source Contracts

Analytics changes must stay aligned with:

- [../phase-2-analytics-observability.md](../phase-2-analytics-observability.md)
- [../phase-2-analytics-metric-model.md](../phase-2-analytics-metric-model.md)
- [../observability-contract.md](../observability-contract.md)
- [../storage-boundaries-and-retention.md](../storage-boundaries-and-retention.md)
- [../secret-handling.md](../secret-handling.md)

## Extension Points

Current analytics implementation surfaces live in:

- `schemas/analytics-aggregate.schema.json`
- `src/higgs_agent/analytics/reporting.py`
- `tests/Contract/test_analytics_aggregate_schema.py`
- `tests/Contract/test_analytics_aggregate_schema_additional.py`
- `tests/Integration/test_analytics_reporting_pipeline.py`

When adding a metric or report view:

1. update the aggregate schema if the output contract changes
2. update the metric-model contract if derivation rules change
3. update implementation and CLI behavior together
4. add contract and integration coverage in the same ticket

## Rules For New Metrics

- Derive metrics from normalized attempt summaries first.
- Use event streams only for reconciliation or backfill when summary data is insufficient.
- Do not introduce dependencies on raw prompts, raw responses, provider payloads, or tool transcripts.
- Prefer normalized dimensions already defined in the aggregate schema and ticket semantics contract.
- Make unavailable local metrics explicit instead of fabricating exact hosted-style usage data.

## Rules For New Report Views

- Keep operator output explainable without provider-specific payload inspection.
- Support filtering and grouping through normalized dimensions rather than ad hoc text matching.
- Preserve `source.export_safe` semantics whenever a report is derived from secret-suspect inputs.
- Do not widen the shareable analytics surface without updating retention and secret-handling docs.

## Recommended Validation

Use the analytics-focused validation stack when changing metrics or report behavior:

```bash
uv run pytest tests/Contract/test_analytics_aggregate_schema.py \
  tests/Contract/test_analytics_aggregate_schema_additional.py \
  tests/Integration/test_analytics_reporting_pipeline.py \
  tests/Unit/test_analytics_reporting.py

uv run ruff check src/higgs_agent/analytics tests/Contract tests/Integration tests/Unit
```

Run broader validation when the change touches shared contracts or CLI behavior.

## Review Triggers

Require tighter review when a change:

- adds new aggregate fields
- changes export-safe behavior
- changes retention or local storage layout
- introduces new dimension names
- uses event payloads where summaries were previously sufficient