# Operator Runbook

## Audience

Operators and reviewers handling HiggsAgent execution runs.

## Purpose

Summarize the safe operating model for the shipped review-mode, autonomous single-ticket, and bounded turnkey-project runtimes.

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
- `uv run higgs-agent run turnkey-project ...`

## Autonomous Single-Ticket Checklist

Before running the autonomous surface, confirm all of the following:

- `OPENROUTER_API_KEY` is set or you will pass `--openrouter-api-key`
- the ticket board validates cleanly
- the target repository has guardrails and write-policy JSON files
- the next ticket is actually `ready` and dependency-unblocked
- the validation commands you pass are the commands you want HiggsAgent to treat as the write-gate evidence source

Use [autonomous-ticket.md](autonomous-ticket.md) for the full command example, telemetry locations, and review expectations.

## Turnkey Project Checklist

Before running the full-project surface, confirm all of the following:

- the board validates cleanly and the repository actually contains executable ready tickets or a resumable checkpoint
- your requirements file gives enough scope for the repository graph rather than a single ticket
- your chosen `--max-tickets` and `--max-consecutive-failures` values reflect how much unattended execution you want to allow
- you understand the current project-level commit policy is `disabled`
- you know where the project checkpoint, summary, and review-bundle files will be written under `.higgs/local/project-runs/`

Use [turnkey-project.md](turnkey-project.md) for the full command shape, terminal conditions, resume flow, and review bundle expectations.

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
- turnkey-project operator prerequisites or recovery flow change