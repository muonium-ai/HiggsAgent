# Instructions For Solving The Game Of Life Sample Project With HiggsAgent

## Purpose

This file is the operator-facing runbook for using HiggsAgent as the framework and process layer while a hosted OpenRouter-backed model implements the Game of Life sample project.

Use this document when you already have the sample project copied into a fresh evaluation repository and want a step-by-step path for:

- wiring HiggsAgent into that repository
- configuring OpenRouter credentials
- choosing the model in your agent runner
- telling the agent exactly what to read and follow
- knowing where execution data and analytics are written so you can verify the run afterward

## Important Boundary

HiggsAgent does not currently ship a first-party end-to-end `solve this repository` runtime command.

Current state of the repository:

- HiggsAgent provides the framework, repository conventions, benchmark workload model, analytics pipeline, and provider abstractions.
- MuonTickets provides the local task system and ticket lifecycle.
- The actual model selection and hosted execution entrypoint are controlled by the outer agent runner you use with OpenRouter.

That means your evaluation stack has three layers:

1. the sample project and its ticket board
2. HiggsAgent as the framework reference and analytics tooling
3. your actual agent runner or editor integration, configured to use an OpenRouter model

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

## Step 1: Add HiggsAgent As A Git Submodule

If you are starting from scratch and want HiggsAgent to create the full evaluation-repository layout for this sample, use the supported bootstrap command from an existing HiggsAgent checkout:

```bash
higgs-agent bootstrap sample-project ../game-of-life-eval --sample-project game-of-life
cd ../game-of-life-eval
```

The rest of this document remains useful after bootstrap, but you can skip the manual submodule and sample-project copy steps.

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
```

## Step 2: Install MuonTickets

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

## Step 3: Validate The Local Game Of Life Ticket Board

From the sample project root:

Using the native binary:

```bash
cd sample-projects/game-of-life
mt validate
```

Using the Python CLI:

```bash
cd sample-projects/game-of-life
uv run --directory ../../tools/higgsagent python3 ../../tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py validate
```

If validation fails, do not start the model run yet.

## Step 4: Configure OpenRouter Credentials

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

## Step 5: Choose The Model

HiggsAgent does not currently define a stable first-party CLI flag or environment variable for selecting the OpenRouter model used by your outer agent runner.

Choose the model in the tool that is actually invoking the agent.

Examples of where model selection usually lives:

- your editor extension or agent UI
- your OpenRouter-backed orchestration wrapper
- your benchmark harness or evaluation runner
- a per-run configuration file in your own tooling

The key rule for fair comparison is:

- keep HiggsAgent revision fixed
- keep the Game of Life requirements and ticket board fixed
- vary only the OpenRouter model between runs

Record the chosen model name explicitly in your run notes.

Examples of model identifiers you might record:

- `anthropic/claude-sonnet-4`
- `openai/gpt-4.1`
- `google/gemini-2.0-flash`

Use the exact model string reported by OpenRouter or by your agent runner.

## Step 6: Recommended Operating Mode

Start with a single-agent baseline first.

Why:

- it tests instruction adherence with the least orchestration noise
- it makes output comparison easier across models
- it reduces variance from multi-agent coordination quality

Only after the single-agent baseline is stable should you move to a coordinator-plus-workers layout.

## Step 7: Exact Instructions To Give The Agent

Give the coding agent a prompt like this:

```text
You are implementing the Game of Life sample project in sample-projects/game-of-life.

Read and follow these sources in order:
1. sample-projects/game-of-life/requirements.md
2. sample-projects/game-of-life/tickets/
3. sample-projects/game-of-life/instructions.md
4. tools/higgsagent documentation and command surface

Rules:
- Treat the Game of Life sample project as the product to build.
- Treat the local ticket board under sample-projects/game-of-life/tickets as the task source of truth.
- Use MuonTickets commands for claim, comment, status changes, and validation.
- Do not hand-edit ticket lifecycle metadata.
- Respect dependencies between tickets.
- Prefer small, reviewable commits.
- Run tests as implementation progresses.
- Keep the project reproducible with uv and pytest.
- Do not modify the HiggsAgent framework unless the evaluation explicitly requires framework changes.

Goal:
Complete the Game of Life sample project against the requirement file and ticket graph.
```

## Step 8: Ticket Workflow During The Run

From `sample-projects/game-of-life/`:

Using the native binary:

```bash
mt ls
mt claim T-000002 --owner coordinator
mt show T-000002
```

Using the Python CLI:

```bash
uv run --directory ../../tools/higgsagent python3 ../../tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py ls
uv run --directory ../../tools/higgsagent python3 ../../tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py claim T-000002 --owner coordinator
uv run --directory ../../tools/higgsagent python3 ../../tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py show T-000002
```

Recommended pattern:

1. validate the board
2. claim one ready ticket
3. implement the ticket
4. add a progress comment
5. run tests relevant to the slice
6. move the ticket to `needs_review`
7. validate the board again

## Step 9: Where Execution Data And Analytics Are Stored

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

## Step 10: What To Inspect To Verify A Run

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

## Step 11: How To Read Analytics With HiggsAgent

HiggsAgent currently exposes analytics reporting through its CLI.

From the evaluation repository root, adjust the paths as needed:

```bash
uv run --directory tools/higgsagent python3 tools/higgsagent/src/higgs_agent/cli.py analytics report \
  --attempt-summaries .higgs/local/analytics/attempt-summaries.ndjson \
  --tickets-dir sample-projects/game-of-life/tickets \
  --group-by provider \
  --group-by model \
  --group-by final_result
```

For JSON output:

```bash
uv run --directory tools/higgsagent python3 tools/higgsagent/src/higgs_agent/cli.py analytics report \
  --attempt-summaries .higgs/local/analytics/attempt-summaries.ndjson \
  --tickets-dir sample-projects/game-of-life/tickets \
  --format json
```

If your environment runs HiggsAgent as an installed package, you can also invoke the equivalent package entrypoint instead of calling the file path directly.

## Step 12: Committed Versus Local State

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

## Recommended Comparison Discipline

For fair model comparisons:

1. use a fresh branch or worktree per model
2. keep the same HiggsAgent submodule revision
3. keep the same Game of Life requirements and ticket set
4. use the same operator prompt and rules
5. record the exact OpenRouter model string
6. compare ticket completion, test pass rate, and resulting diffs

## Common Mistakes

- letting the agent modify the HiggsAgent framework instead of the sample project
- mixing the main repository ticket board with the sample-project ticket board
- forgetting to load `OPENROUTER_API_KEY`
- changing multiple evaluation variables at once
- committing local telemetry or raw provider data
- assuming HiggsAgent currently provides a turnkey project-solving CLI

## Minimal Operator Checklist

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