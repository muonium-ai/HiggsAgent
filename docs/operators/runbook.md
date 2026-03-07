# Operator Runbook

## Audience

Operators and reviewers handling HiggsAgent execution runs.

## Purpose

Summarize the safe operating model for the shipped review-mode and autonomous single-ticket runtimes.

## Operating Rules

- Start from validated ticket state.
- Prefer explicit, bounded execution surfaces rather than ad hoc repository mutation.
- Treat protected paths and secret-suspect output as review-only events.
- Use the review handoff template when automation cannot complete safely.

## Installed Command Surface

Operators should use the installed HiggsAgent CLI from the repository environment:

- `uv run higgs-agent validate tickets`
- `uv run higgs-agent analytics report ...`
- `uv run higgs-agent bootstrap sample-project ...`
- `uv run higgs-agent run ticketed-project ...`
- `uv run higgs-agent run autonomous-ticket ...`

## Autonomous Single-Ticket Checklist

Before running the autonomous surface, confirm all of the following:

- `OPENROUTER_API_KEY` is set or you will pass `--openrouter-api-key`
- the ticket board validates cleanly
- the target repository has guardrails and write-policy JSON files
- the next ticket is actually `ready` and dependency-unblocked
- the validation commands you pass are the commands you want HiggsAgent to treat as the write-gate evidence source

Use [autonomous-ticket.md](autonomous-ticket.md) for the full command example, telemetry locations, and review expectations.

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
- autonomous operator prerequisites or review flow change