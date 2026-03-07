# Operator Runbook

## Audience

Operators and reviewers handling HiggsAgent execution runs.

## Purpose

Summarize the safe operating model before the full runtime exists.

## Operating Rules

- Start from validated ticket state.
- Prefer read-only execution until the write gate is explicitly allowed.
- Treat protected paths and secret-suspect output as review-only events.
- Use the review handoff template when automation cannot complete safely.

## Installed Command Surface

Operators should use the installed HiggsAgent CLI from the repository environment:

- `uv run higgs-agent validate tickets`
- `uv run higgs-agent analytics report ...`
- `uv run higgs-agent bootstrap sample-project ...`
- `uv run higgs-agent run ticketed-project ...`

## Normative Sources

- [../safety-model.md](../safety-model.md)
- [../review-handoff-template.md](../review-handoff-template.md)
- [../observability-contract.md](../observability-contract.md)

## Analytics Notes

- Generate analytics reports from local normalized attempt summaries, not raw provider payloads.
- Treat any aggregate output with `source.export_safe=false` as review-only.
- Use [analytics.md](analytics.md) for report commands, sharing boundaries, and retention expectations.

## Update When

- review triggers change
- write boundaries change
- execution artifact handling changes