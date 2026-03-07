# Turnkey Project Build

## Audience

Operators and reviewers running HiggsAgent across an entire repository ticket graph.

## Purpose

Explain how to invoke, resume, monitor, and review `uv run higgs-agent run turnkey-project` for bounded full-project autonomous builds.

## Current Boundary

The current turnkey runtime builds on the Phase 6 single-ticket loop instead of replacing it.

- It repeatedly invokes the shipped autonomous single-ticket runtime.
- It stops when there are no more ready tickets, the graph is blocked, validation fails, a review handoff is required, runtime failures exceed the configured bound, or the operator-configured ticket limit is reached.
- It persists a checkpoint, summary, and review bundle for every project run.
- It defaults to `commit_policy=disabled` and currently rejects `--create-local-commit` because local commit creation is not shipped yet.

This means the command is suitable for bounded repository builds, but it is still review-first and intentionally conservative.

## Prerequisites

- Python 3.12+ and `uv`
- a repository with HiggsAgent-compatible layout and a valid MuonTickets board
- guardrails and write-policy JSON files
- a requirements or project-context file with enough project-level scope for the ticket graph
- an OpenRouter API key available through `OPENROUTER_API_KEY` or `--openrouter-api-key`
- at least one explicit validation command

## Command Example

```bash
export OPENROUTER_API_KEY=...

uv run higgs-agent run turnkey-project \
  --repo-root . \
  --requirements docs/architecture.md \
  --tickets-dir tickets \
  --guardrails config/guardrails.example.json \
  --write-policy config/write-policy.example.json \
  --validation-command "uv run pytest tests" \
  --validation-command "uv run ruff check src tests" \
  --max-tickets 5 \
  --max-consecutive-failures 2
```

Resume an interrupted run:

```bash
uv run higgs-agent run turnkey-project \
  --repo-root . \
  --requirements docs/architecture.md \
  --tickets-dir tickets \
  --guardrails config/guardrails.example.json \
  --write-policy config/write-policy.example.json \
  --validation-command "uv run pytest tests" \
  --project-run-id project-run-abc123 \
  --resume
```

## Operator Controls

- `--project-run-id` gives the run a stable identifier for checkpointing and later resume.
- `--resume` continues an existing checkpoint instead of creating a new project run.
- `--max-tickets` stops after a bounded number of attempted ticket slices.
- `--max-consecutive-failures` bounds retry behavior for runtime-level failures.
- `--owner` overrides the MuonTickets claim owner. The default is `coordinator`.
- `--muontickets-cli` overrides the default MuonTickets path.
- `--create-local-commit` is visible as an explicit policy surface, but the current runtime rejects it because local commit creation is not yet implemented.

## Telemetry And Review Artifacts

Each project run writes local-only artifacts under `.higgs/local/project-runs/<project_run_id>/`.

- Checkpoint: `.higgs/local/project-runs/<project_run_id>/checkpoint.json`
- Summary: `.higgs/local/project-runs/<project_run_id>/summary.json`
- Review bundle: `.higgs/local/project-runs/<project_run_id>/review-bundle.json`

The underlying single-ticket attempts still write their normal attempt-level artifacts under `.higgs/local/runs/<run_id>/<attempt_id>/` and append attempt summaries to `.higgs/local/analytics/attempt-summaries.ndjson`.

## Terminal Conditions

Operators should treat these terminal conditions as the authoritative end-state explanation:

- `no_ready_ticket`: the project run finished because there are no more eligible ready tickets
- `blocked_dependency_graph`: no ticket is ready because dependencies remain incomplete or missing
- `validation_failure`: a ticket attempt failed the configured validation commands
- `review_handoff_required`: a ticket attempt produced a write-gate handoff that requires review
- `ticket_rejected`: a ticket attempt failed the write gate without a handoff path
- `repeated_failures_exceeded`: runtime-level failures exceeded the configured consecutive-failure bound
- `max_ticket_limit_reached`: the operator-configured ticket-attempt limit was reached

## Review And Recovery Flow

1. Run `uv run higgs-agent validate tickets` before starting the project build.
2. Start `uv run higgs-agent run turnkey-project ...` with explicit requirements, policy, and validation inputs.
3. Read the CLI summary for `project_run_id`, `status`, `terminal_condition`, `retry_count`, and the emitted checkpoint, summary, and review-bundle paths.
4. Inspect `.higgs/local/project-runs/<project_run_id>/review-bundle.json` to see completed, blocked, and untouched tickets.
5. If the run stopped due to `max_ticket_limit_reached` or an external interruption, rerun with `--project-run-id ... --resume`.
6. If the run stopped due to validation failure, handoff, or a blocked graph, resolve the underlying ticket or dependency issue before retrying.
7. Review changed files and underlying attempt artifacts before merging or advancing workflow state beyond `needs_review`.

## Current Limits

- The runtime remains review-first; it does not auto-complete tickets to `done`.
- Only the already shipped structured materialization formats are supported by the underlying single-ticket runtime.
- Project-level local commit creation is not implemented yet.
- The runtime is bounded to a single local repository and does not coordinate distributed workers or deployment steps.

## Normative Sources

- [../phase-7-turnkey-project-build.md](../phase-7-turnkey-project-build.md)
- [../autonomous-coding-session-contract.md](../autonomous-coding-session-contract.md)
- [../runtime-tooling.md](../runtime-tooling.md)
- [../safety-model.md](../safety-model.md)