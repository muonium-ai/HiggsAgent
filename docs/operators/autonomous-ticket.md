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
- It materializes bounded directory creation, full-file writes, and exact-match follow-up patches.
- It runs the configured validation commands against the mutated workspace.
- It evaluates the resulting change set through the write gate.
- It comments on the ticket and moves successful or handoff-required results to `needs_review`.

The current runtime does not yet complete an entire ticket graph in one command, and it does not support arbitrary diff formats, fuzzy merges, or tool-driven edit sessions outside the structured materialization formats documented below.

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

## Supported Materialization Formats

The autonomous runtime expects one JSON object with a short `summary` plus at least one supported mutation section.

Top-level scaffold response:

```json
{
  "summary": "Create the initial package scaffold",
  "directories": ["src/game_of_life", "tests"],
  "writes": [
    {
      "path": "src/game_of_life/__init__.py",
      "content": "\"\"\"Game of Life package.\"\"\"\n"
    },
    {
      "path": "tests/test_engine.py",
      "content": "def test_placeholder():\n    assert True\n"
    }
  ]
}
```

Nested scaffold response:

```json
{
  "summary": "Create the Game of Life scaffold",
  "scaffold": {
    "tree": [
      {
        "type": "directory",
        "path": "src",
        "children": [
          {
            "type": "directory",
            "path": "game_of_life",
            "children": [
              {
                "type": "file",
                "path": "engine.py",
                "content": "def next_state(board):\n    return board\n"
              }
            ]
          }
        ]
      },
      {
        "type": "directory",
        "path": "fixtures",
        "children": [
          {
            "type": "file",
            "path": "blinker.txt",
            "text": ".#.\n.#.\n.#.\n"
          }
        ]
      }
    ]
  }
}
```

Follow-up patch response:

```json
{
  "summary": "Teach the engine to rotate a blinker",
  "patches": [
    {
      "path": "src/game_of_life/engine.py",
      "before": "    return board\n",
      "after": "    if board == [\".#.\", \".#.\", \".#.\"]:\n        return [\"...\", \"###\", \"...\"]\n    return board\n"
    }
  ]
}
```

Supported aliases and constraints:

- `files` is accepted as an alias for top-level `writes`.
- `text` is accepted as an alias for file `content`.
- `diffs` is accepted as an alias for `patches`.
- Patch entries must target an existing file and replace exactly one matched snippet.
- Duplicate directories, duplicate writes, duplicate patches, and overlapping write-plus-patch targets are rejected before any filesystem mutation begins.

## Direct Materialization Versus Human Intervention

HiggsAgent can materialize a response directly when all of the following are true:

- the response is valid JSON using the supported scaffold or patch shapes
- every path is repository-relative and remains inside the repository root
- every patch target exists and the `before` snippet matches exactly one location
- the inferred changed paths stay within write-policy limits and allowed paths
- configured validation commands pass after materialization

Human intervention is still required when any of the following happens:

- the model returns freeform prose, malformed JSON, or unsupported edit instructions
- a patch target is missing, absent from the current file contents, or matches multiple locations
- the write gate requires review because of protected paths, suspicious secrets, or policy-limit violations
- validation commands fail after the workspace mutation

Rejected materialization and validation failures do not auto-advance the ticket. Handoff-required results still move to `needs_review` and include review artifacts for the operator.

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
- `materialization-plan.json` when HiggsAgent parsed scaffold writes or patch operations
- `review-handoff.txt` when the write gate requires human review or explains a blocked outcome

Common materialization event types:

- `directory.created` for normalized scaffold directory creation
- `file.written` for full-file scaffold writes
- `file.patched` for exact-match follow-up patch application

In a Game of Life-style flow, the first run can create `src/game_of_life/engine.py`, `tests/test_engine.py`, and `fixtures/blinker.txt`, while a later run can emit `file.patched` events and patch entries in `materialization-plan.json` for incremental edits to those files.

The CLI also prints the relative event, artifact, and attempt-summary paths after each run so operators can jump directly to the relevant records.

## Expected Outcomes

- `validation_decision=accepted`: the write gate accepted the inferred change set and HiggsAgent moved the ticket to `needs_review`
- `validation_decision=handoff_required`: HiggsAgent wrote the review-handoff artifact and still moved the ticket to `needs_review`
- `validation_decision=rejected`: HiggsAgent commented on the ticket with the blocking reason and did not auto-advance it

## Review Flow

1. Run `uv run higgs-agent validate tickets` before starting.
2. Invoke `uv run higgs-agent run autonomous-ticket ...` with explicit repo, policy, and validation inputs.
3. Review the CLI summary for ticket id, execution status, validation decision, changed paths, and telemetry locations.
4. Inspect the changed files, `materialization-plan.json`, and `events.ndjson` to confirm the scaffold or patch operations match the ticket intent.
5. If the result is in `needs_review`, complete the repository's normal review workflow through MuonTickets and Git.

## Normative Sources

- [../autonomous-coding-session-contract.md](../autonomous-coding-session-contract.md)
- [../phase-6-autonomous-ticket-execution.md](../phase-6-autonomous-ticket-execution.md)
- [../runtime-tooling.md](../runtime-tooling.md)
- [../safety-model.md](../safety-model.md)