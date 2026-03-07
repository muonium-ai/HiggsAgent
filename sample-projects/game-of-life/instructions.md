# Instructions For Solving The Game Of Life Sample Project With HiggsAgent

## Purpose

This file is the operator-facing runbook for using HiggsAgent as the framework and process layer while an agent implements the Game of Life sample project in a separate evaluation repository.

Use this document when you already have the sample project copied into a fresh evaluation repository and want a step-by-step path for:

- wiring HiggsAgent into that repository
- using the currently implemented HiggsAgent CLI surface
- configuring OpenRouter credentials
- choosing the routed model configuration
- telling an implementation agent exactly what to read and follow
- running ticket-by-ticket implementation in a second repository
- knowing where execution data and analytics are written so you can verify the run afterward

## Important Boundary

HiggsAgent now ships a first-party operator CLI, but it still does not ship a one-command autonomous `solve this repository` runtime.

Current state of the repository:

- HiggsAgent provides the framework, repository conventions, bootstrap flow, ticket validation wrapper, review-mode dispatcher runtime, analytics pipeline, and provider abstractions.
- MuonTickets provides the local task system and ticket lifecycle.
- The actual implementation loop is still driven by the outer coding agent or editor integration you use with OpenRouter.

That means your evaluation stack has three layers:

1. the sample project and its ticket board
2. HiggsAgent as the framework reference, CLI surface, and analytics tooling
3. your actual coding agent or editor integration, configured to use an OpenRouter model

What exists today:

- `higgs-agent bootstrap sample-project` creates the evaluation-repository layout for the shipped sample project
- `higgs-agent validate tickets` validates a MuonTickets board from the installed HiggsAgent CLI
- `higgs-agent run ticketed-project` runs the deterministic dispatcher for the next ready ticket in explicit review mode
- `higgs-agent analytics report` renders analytics from normalized attempt summaries

What does not exist yet:

- a turnkey command that autonomously edits the project, infers the changed-file set, runs tests, updates ticket lifecycle, and loops until the app is complete without an outer agent

## What The Agent Must Treat As Source Of Truth

The coding agent should read and follow these in order:

1. `sample-projects/game-of-life/requirements.md`
2. `sample-projects/game-of-life/tickets/`
3. this file
4. the HiggsAgent submodule documentation and command surface

The agent must treat the Game of Life project as the product to build.

It must not treat the HiggsAgent framework repository itself as the product target.

## Repository Layout Assumed By This Guide

Recommended evaluation repository layout:

```text
evaluation-repo/
  .env
  sample-projects/
    game-of-life/
      requirements.md
      instructions.md
      tickets/
  tools/
    higgsagent/
  bin/
    mt
  .higgs/
    local/
      runs/
      analytics/
```

You can use a different layout, but the rest of the instructions assume the paths above.

## Step 1: Create The Evaluation Repository

Preferred path: bootstrap from an existing HiggsAgent checkout that already has its `uv` environment synced.

```bash
cd /path/to/HiggsAgent
uv sync --extra dev
uv run higgs-agent bootstrap sample-project ../game-of-life-eval --sample-project game-of-life
cd ../game-of-life-eval
```

This creates the recommended layout, adds `tools/higgsagent` as a submodule, copies the Game of Life sample project, creates `.higgs/local/` directories, and validates the copied ticket board.

Manual fallback: if you are not using bootstrap, create the evaluation repository yourself and then continue with the submodule flow below.

## Step 2: Add HiggsAgent As A Git Submodule Manually

From the root of your evaluation repository:

```bash
git submodule add https://github.com/muonium-ai/HiggsAgent.git tools/higgsagent
git submodule update --init --recursive
```

Then initialize the HiggsAgent environment:

```bash
cd tools/higgsagent
uv sync --extra dev
cd ../..
```

Verify the framework is present:

```bash
test -f tools/higgsagent/pyproject.toml
test -f tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py
uv run --directory tools/higgsagent higgs-agent --help
```

## Step 3: Choose How To Run MuonTickets

You have two valid options.

### Option A: Use A Native MuonTickets Binary

This is the most convenient path for evaluation runs because it avoids invoking the Python ticket CLI directly for every board operation.

Download the correct binary from MuonTickets GitHub releases and place it in `bin/`.

Template flow:

```bash
mkdir -p bin
curl -L -o /tmp/mt-release.tar.gz "https://github.com/muonium-ai/muontickets/releases/download/<tag>/mt-rust-<arch>-<os>.tar.gz"
tar -xzf /tmp/mt-release.tar.gz -C bin
chmod +x bin/*
export PATH="$PWD/bin:$PATH"
```

Then verify:

```bash
mt --version
```

### Option B: Use The MuonTickets Python CLI Shipped Through HiggsAgent

If you do not want a native binary, use the submodule-managed Python entrypoint:

```bash
uv run --directory tools/higgsagent python3 tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py --version
```

Both options are acceptable. Pick one and stay consistent throughout a model comparison run.

## Step 4: Validate The Local Game Of Life Ticket Board

From the sample project root:

Using the native binary:

```bash
cd sample-projects/game-of-life
mt validate
```

Using the Python CLI:

```bash
uv run --directory tools/higgsagent higgs-agent validate tickets --repo-root sample-projects/game-of-life
```

If validation fails, do not start the model run yet.

## Step 5: Configure OpenRouter Credentials

Create a local environment file in the evaluation repository root.

Minimum `.env`:

```bash
cat > .env <<'EOF'
OPENROUTER_API_KEY=your_openrouter_key_here
HIGGS_ENV=development
HIGGS_WRITE_MODE=review
EOF
```

Load it into your shell:

```bash
set -a
source .env
set +a
```

You can also export the variables directly:

```bash
export OPENROUTER_API_KEY="your_openrouter_key_here"
export HIGGS_ENV=development
export HIGGS_WRITE_MODE=review
```

### What These Variables Mean

- `OPENROUTER_API_KEY`: credential for hosted model access through OpenRouter
- `HIGGS_ENV=development`: development-oriented environment mode
- `HIGGS_WRITE_MODE=review`: safe evaluation default; keep human review explicit

Do not commit `.env` files with real keys.

## Step 6: Choose The Model

HiggsAgent now exposes a first-party model-selection surface through the guardrails config used by the routing policy.

Set the OpenRouter model identifiers in `config/guardrails.json` or your evaluation-specific copy of the guardrails file.

Minimum routing section:

```json
{
  "routing": {
    "economy": {"provider": "openrouter", "model_id": "openai/gpt-4.1-mini", "estimated_cost_usd": 0.40},
    "balanced": {"provider": "openrouter", "model_id": "openai/gpt-4.1", "estimated_cost_usd": 2.50},
    "deep": {"provider": "openrouter", "model_id": "anthropic/claude-sonnet-4", "estimated_cost_usd": 5.00}
  }
}
```

HiggsAgent records the selected provider and model from that routing decision in execution events and attempt summaries, so the analytics output reflects the configured OpenRouter model directly.

Your outer agent runner still needs to use the same provider and model family in practice.

Examples of where model selection usually lives:

- your editor extension or agent UI
- your OpenRouter-backed orchestration wrapper
- your benchmark harness or evaluation runner
- a per-run configuration file in your own tooling

The key rule for fair comparison is:

- keep HiggsAgent revision fixed
- keep the Game of Life requirements and ticket board fixed
- vary only the OpenRouter model between runs

Record the chosen guardrails revision or copied config file alongside your run notes.

Examples of model identifiers you might record:

- `anthropic/claude-sonnet-4`
- `openai/gpt-4.1`
- `google/gemini-2.0-flash`

Use the exact model string reported by OpenRouter or by your agent runner.

## Step 7: Recommended Operating Mode

Start with a single-agent baseline first.

Why:

- it tests instruction adherence with the least orchestration noise
- it makes output comparison easier across models
- it reduces variance from multi-agent coordination quality

Only after the single-agent baseline is stable should you move to a coordinator-plus-workers layout.

## Step 8: Step-By-Step Build Flow For An Agent In A Different Repository

Use this sequence when the implementation agent is operating in the separate evaluation repository instead of inside the HiggsAgent framework repository.

1. Create or bootstrap the evaluation repository.

  Preferred:

  ```bash
  cd /path/to/HiggsAgent
  uv run higgs-agent bootstrap sample-project ../game-of-life-eval --sample-project game-of-life
  cd ../game-of-life-eval
  ```

2. Sync the HiggsAgent submodule environment.

  ```bash
  uv run --directory tools/higgsagent higgs-agent --help
  ```

  If that command fails because dependencies are missing:

  ```bash
  uv sync --directory tools/higgsagent --extra dev
  uv run --directory tools/higgsagent higgs-agent --help
  ```

3. Load credentials.

  ```bash
  set -a
  source .env
  set +a
  ```

4. Validate the Game of Life ticket board.

  ```bash
  uv run --directory tools/higgsagent higgs-agent validate tickets --repo-root sample-projects/game-of-life
  ```

5. Read the project sources of truth in this exact order.

  - `sample-projects/game-of-life/requirements.md`
  - `sample-projects/game-of-life/tickets/`
  - `sample-projects/game-of-life/instructions.md`
  - `tools/higgsagent/docs/`

6. Claim one ready ticket on the sample-project board and inspect it before writing code.

  Using the native binary:

  ```bash
  cd sample-projects/game-of-life
  mt ls
  mt claim T-000002 --owner coordinator
  mt show T-000002
  cd ../..
  ```

  Using the Python CLI:

  ```bash
  uv run --directory tools/higgsagent python3 tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py ls --tickets-dir sample-projects/game-of-life/tickets
  uv run --directory tools/higgsagent python3 tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py claim T-000002 --owner coordinator --tickets-dir sample-projects/game-of-life/tickets
  uv run --directory tools/higgsagent python3 tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py show T-000002 --tickets-dir sample-projects/game-of-life/tickets
  ```

7. Implement only the claimed ticket inside the sample-project repository surfaces, not inside `tools/higgsagent`.

  Typical target paths:

  - `src/`
  - `tests/`
  - `README.md`
  - `pyproject.toml` for the sample project only if the ticket requires it

8. Run the narrowest relevant tests for the ticket slice.

  Example:

  ```bash
  uv run pytest tests
  ```

9. Record the proposed change set and validation summary, then run the explicit HiggsAgent dispatcher surface if you want an inspectable dispatcher attempt for the ticket.

  Template:

  ```bash
  uv run --directory tools/higgsagent higgs-agent run ticketed-project \
    --repo-root sample-projects/game-of-life \
    --requirements sample-projects/game-of-life/requirements.md \
    --tickets-dir sample-projects/game-of-life/tickets \
    --guardrails tools/higgsagent/config/guardrails.example.json \
    --write-policy tools/higgsagent/config/write-policy.example.json \
    --changed-file src/game_of_life/board.py:40:0 \
    --validation-summary "uv run pytest tests passed for the claimed ticket"
  ```

  This command does not mutate the repository automatically. It records an explicit dispatcher attempt using the next ready ticket plus the change set and validation summary you provide.

10. Update the sample-project ticket lifecycle.

  Recommended sequence:

  - add a progress comment
  - move the ticket to `needs_review`
  - re-run board validation

11. Repeat one ticket at a time until the Game of Life project is complete.

12. After the run, inspect `.higgs/local/analytics/attempt-summaries.ndjson` and the attempt-level run artifacts before comparing models or declaring success.

## Step 9: Exact Instructions To Give The Agent

If you want a first-party HiggsAgent execution surface instead of driving the run entirely through an external prompt UI, use `higgs-agent run ticketed-project` with explicit repository inputs, a declared proposed change set, and a validation summary.

Template:

```bash
uv run --directory tools/higgsagent higgs-agent run ticketed-project \
  --repo-root sample-projects/game-of-life \
  --requirements sample-projects/game-of-life/requirements.md \
  --tickets-dir sample-projects/game-of-life/tickets \
  --guardrails tools/higgsagent/config/guardrails.example.json \
  --write-policy tools/higgsagent/config/write-policy.example.json \
  --changed-file src/game_of_life/board.py:40:0 \
  --validation-summary "pytest tests/Unit passed for board model slice"
```

This command runs the existing deterministic dispatcher pipeline for the next ready ticket. It does not infer repository mutations for you; the proposed change set and validation summary are explicit inputs to the write gate.

When the command completes, inspect the concrete local outputs under `.higgs/local/runs/<run_id>/<attempt_id>/events.ndjson`, `.higgs/local/runs/<run_id>/<attempt_id>/artifacts/`, and `.higgs/local/analytics/attempt-summaries.ndjson`.

Give the coding agent a prompt like this:

```text
You are implementing the Game of Life sample project in a separate evaluation repository.

Read and follow these sources in order:
1. sample-projects/game-of-life/requirements.md
2. sample-projects/game-of-life/tickets/
3. sample-projects/game-of-life/instructions.md
4. tools/higgsagent documentation and command surface

Rules:
- Treat the Game of Life sample project as the product to build.
- Treat the local ticket board under sample-projects/game-of-life/tickets as the task source of truth.
- Work only in the evaluation repository surfaces for the sample project unless the task explicitly requires framework work.
- Use MuonTickets commands for claim, comment, status changes, and validation.
- Do not hand-edit ticket lifecycle metadata.
- Respect dependencies between tickets.
- Prefer small, reviewable commits.
- Run tests as implementation progresses.
- Keep the project reproducible with uv and pytest.
- Do not modify the HiggsAgent framework unless the evaluation explicitly requires framework changes.
- After each completed slice, record the validation summary and inspect `.higgs/local` telemetry if you run `higgs-agent run ticketed-project`.

Goal:
Complete the Game of Life sample project against the requirement file and ticket graph.
```

## Step 10: Ticket Workflow During The Run

From `sample-projects/game-of-life/`:

Using the native binary:

```bash
mt ls
mt claim T-000002 --owner coordinator
mt show T-000002
```

Using the Python CLI:

```bash
uv run --directory tools/higgsagent python3 tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py ls --tickets-dir sample-projects/game-of-life/tickets
uv run --directory tools/higgsagent python3 tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py claim T-000002 --owner coordinator --tickets-dir sample-projects/game-of-life/tickets
uv run --directory tools/higgsagent python3 tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py show T-000002 --tickets-dir sample-projects/game-of-life/tickets
```

Recommended pattern:

1. validate the board
2. claim one ready ticket
3. implement the ticket
4. add a progress comment
5. run tests relevant to the slice
6. move the ticket to `needs_review`
7. validate the board again

## Step 11: Where Execution Data And Analytics Are Stored

HiggsAgent’s storage contract separates committed repository state from local execution artifacts.

### Local-Only Execution Data

Recommended local paths:

- `.higgs/local/runs/<run_id>/<attempt_id>/events.ndjson`
- `.higgs/local/runs/<run_id>/<attempt_id>/artifacts/`
- `.higgs/local/analytics/attempt-summaries.ndjson`
- `.higgs/local/analytics/aggregates/<window>.ndjson`
- `.higgs/local/analytics/exports/<generated_at>.json`

These are local inspection paths and should not be committed.

### What Each Path Contains

`.higgs/local/runs/<run_id>/<attempt_id>/events.ndjson`

- append-only event stream for a specific attempt
- lifecycle events such as execution creation, provider request, provider response, validation, write-gate decisions, retries, and completion

`.higgs/local/runs/<run_id>/<attempt_id>/artifacts/`

- local artifacts referenced by events
- tool output files, hashes, and derived execution artifacts when a runner persists them

`.higgs/local/analytics/attempt-summaries.ndjson`

- one normalized summary record per attempt
- the stable analytics-facing data source
- includes provider, model, final result, retry count, tool-call count, usage, and normalized error info

`.higgs/local/analytics/aggregates/<window>.ndjson`

- derived rollups for a reporting window
- useful for batch comparisons after multiple runs

`.higgs/local/analytics/exports/<generated_at>.json`

- export-friendly analytics snapshots
- use these when you want to compare or archive sanitized summaries outside the raw local run directory

## Step 12: What To Inspect To Verify A Run

After a model run, inspect these in order:

1. the Game of Life ticket board state
2. the local git diff or commit history in the sample project
3. the test results for the sample project
4. `.higgs/local/analytics/attempt-summaries.ndjson`
5. attempt-level `events.ndjson` for the run you care about

Practical checks:

- were the right tickets claimed and advanced in order?
- did the model leave clean, reviewable commits?
- did the implementation satisfy the sample project tests?
- which provider and model identifiers were recorded in the attempt summaries?
- were there retries, provider failures, or validation failures?

## Step 13: How To Read Analytics With HiggsAgent

HiggsAgent currently exposes analytics reporting through its CLI.

From the evaluation repository root, adjust the paths as needed:

```bash
uv run --directory tools/higgsagent higgs-agent analytics report \
  --attempt-summaries .higgs/local/analytics/attempt-summaries.ndjson \
  --tickets-dir sample-projects/game-of-life/tickets \
  --group-by provider \
  --group-by model \
  --group-by final_result
```

For JSON output:

```bash
uv run --directory tools/higgsagent higgs-agent analytics report \
  --attempt-summaries .higgs/local/analytics/attempt-summaries.ndjson \
  --tickets-dir sample-projects/game-of-life/tickets \
  --format json
```

If you have installed HiggsAgent into a different environment, use the equivalent installed `higgs-agent analytics report` command from that environment instead.

## Step 14: Committed Versus Local State

What should remain committed in git:

- requirements
- instructions
- tickets
- source code produced by the run
- tests
- README updates
- intentionally exported sanitized summaries, only if you explicitly choose to keep them

What should remain local-only:

- raw prompts
- raw provider responses
- provider payloads and headers
- tool stdout and stderr
- full event streams
- debug traces

## Step 15: Recommended Comparison Discipline

For fair model comparisons:

1. use a fresh branch or worktree per model
2. keep the same HiggsAgent submodule revision
3. keep the same Game of Life requirements and ticket set
4. use the same operator prompt and rules
5. record the exact OpenRouter model string
6. compare ticket completion, test pass rate, and resulting diffs

## Step 16: Common Mistakes

- letting the agent modify the HiggsAgent framework instead of the sample project
- mixing the main repository ticket board with the sample-project ticket board
- forgetting to load `OPENROUTER_API_KEY`
- changing multiple evaluation variables at once
- committing local telemetry or raw provider data
- assuming HiggsAgent currently provides a turnkey project-solving CLI
- running the dispatcher against the wrong repo root instead of the sample-project evaluation repository

## Step 17: Minimal Operator Checklist

- [ ] HiggsAgent added as `tools/higgsagent` submodule
- [ ] HiggsAgent environment synced with `uv`
- [ ] MuonTickets installed either as a binary or via the Python CLI path
- [ ] `OPENROUTER_API_KEY` loaded into the environment
- [ ] chosen OpenRouter model recorded outside the agent run
- [ ] Game of Life board validated before starting
- [ ] agent prompt points to `requirements.md`, `tickets/`, and this file
- [ ] post-run verification includes ticket state, tests, and `.higgs/local/analytics/attempt-summaries.ndjson`

## Final Recommendation

For the first pass, run one model from start to finish against the Game of Life ticket board and inspect the local analytics output afterward. Once that baseline is stable, repeat the same run with other OpenRouter models and compare results without changing the requirements, ticket graph, or HiggsAgent revision.