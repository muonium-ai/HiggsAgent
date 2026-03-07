# Autonomous Single-Ticket Execution

## Audience

Operators and reviewers running the first-party autonomous coding loop.

## Purpose

Explain how to invoke, observe, and review `uv run higgs-agent run autonomous-ticket` against one repository and one ready ticket at a time.

## Current Boundary

The current autonomous runtime is intentionally narrow.

- It selects the next dependency-unblocked `ready` ticket from the configured tickets directory.
- It claims the ticket through MuonTickets.
- It calls OpenRouter for a structured JSON action plan.
- It materializes bounded directory creation and full-file writes.
- It runs the configured validation commands against the mutated workspace.
- It evaluates the resulting change set through the write gate.
- It comments on the ticket and moves successful or handoff-required results to `needs_review`.

The current runtime does not yet complete an entire ticket graph in one command, and it does not yet support general iterative patch application beyond the structured materialization formats already implemented.

## Prerequisites

- Python 3.12+ and `uv`
- a repository with HiggsAgent-compatible layout and a valid MuonTickets board
- a ready ticket with dependencies already satisfied
- a requirements or project-context file to include in the autonomous prompt
- guardrails and write-policy JSON files
- an OpenRouter API key available through `OPENROUTER_API_KEY` or `--openrouter-api-key`
- at least one explicit validation command

## Command Example

```bash
export OPENROUTER_API_KEY=...

uv run higgs-agent run autonomous-ticket \
  --repo-root . \
  --requirements docs/architecture.md \
  --tickets-dir tickets \
  --guardrails config/guardrails.example.json \
  --write-policy config/write-policy.example.json \
  --validation-command "uv run pytest" \
  --validation-command "uv run ruff check src tests"
```

Optional controls:

- `--owner` overrides the MuonTickets claim owner. The default is `coordinator`.
- `--muontickets-cli` overrides the default MuonTickets path of `tickets/mt/muontickets/muontickets/mt.py`.
- `--openrouter-api-key` can be used instead of the environment variable.

## What HiggsAgent Automates

- selecting the next ready ticket
- claiming the ticket through MuonTickets
- reading repository context for the prompt
- turning the OpenRouter response into bounded workspace mutations
- inferring the changed-path set from observed writes instead of CLI placeholders
- generating validation evidence from actual command results
- appending ticket comments for success or blocked outcomes
- moving successful and handoff-required runs to `needs_review`

## What Still Requires Operator Review

- reviewing the changed files before merge or further promotion
- resolving any handoff-required result caused by protected paths or other write-policy checks
- deciding whether the repository policy should allow broader materialization formats later
- deciding whether a failed validation result should be retried, fixed manually, or split into follow-up work
- completing any workflow after `needs_review`, including `done` and archive actions

## Telemetry And Review Artifacts

Autonomous runs persist local telemetry under `.higgs/local/`.

- Events: `.higgs/local/runs/<run_id>/<attempt_id>/events.ndjson`
- Artifacts directory: `.higgs/local/runs/<run_id>/<attempt_id>/artifacts/`
- Attempt summaries: `.higgs/local/analytics/attempt-summaries.ndjson`

Common artifacts:

- `output.txt` when the provider returned output text
- `review-handoff.txt` when the write gate requires human review or explains a blocked outcome

The CLI also prints the relative event, artifact, and attempt-summary paths after each run so operators can jump directly to the relevant records.

## Expected Outcomes

- `validation_decision=accepted`: the write gate accepted the inferred change set and HiggsAgent moved the ticket to `needs_review`
- `validation_decision=handoff_required`: HiggsAgent wrote the review-handoff artifact and still moved the ticket to `needs_review`
- `validation_decision=rejected`: HiggsAgent commented on the ticket with the blocking reason and did not auto-advance it

## Review Flow

1. Run `uv run higgs-agent validate tickets` before starting.
2. Invoke `uv run higgs-agent run autonomous-ticket ...` with explicit repo, policy, and validation inputs.
3. Review the CLI summary for ticket id, execution status, validation decision, changed paths, and telemetry locations.
4. Inspect the changed files and `.higgs/local` artifacts.
5. If the result is in `needs_review`, complete the repository's normal review workflow through MuonTickets and Git.

## Normative Sources

- [../autonomous-coding-session-contract.md](../autonomous-coding-session-contract.md)
- [../phase-6-autonomous-ticket-execution.md](../phase-6-autonomous-ticket-execution.md)
- [../runtime-tooling.md](../runtime-tooling.md)
- [../safety-model.md](../safety-model.md)