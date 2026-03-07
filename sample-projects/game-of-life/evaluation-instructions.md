# Game of Life Evaluation Instructions

## Purpose

This guide explains how to use the Game of Life sample project as a reproducible evaluation target for HiggsAgent.

The intended workflow is:

1. create or clone an evaluation repository
2. add HiggsAgent as a git submodule
3. install MuonTickets tooling from GitHub releases as native binaries
4. configure the OpenRouter API key and local environment
5. point an agent at the Game of Life requirements and local ticket board
6. run the implementation with different models and compare results

This document is written for evaluators who want a stable benchmark project with explicit requirements, explicit tickets, and a repeatable setup path.

## What This Sample Contains

The Game of Life sample project already includes:

- a detailed product specification in [requirements.md](requirements.md)
- a local MuonTickets board under [tickets](tickets)
- more than 10 meaningful tickets that can be executed in parallel after scaffolding
- a dependency graph designed to test coordination, ticket adherence, and implementation quality

The sample project is intentionally small enough to finish quickly and rich enough to expose instruction-following differences across models.

## Recommended Evaluation Layout

Use a dedicated repository or workspace for evaluation runs.

Recommended layout:

```text
evaluation-repo/
  sample-projects/
    game-of-life/
      requirements.md
      evaluation-instructions.md
      tickets/
  tools/
    higgsagent/
  bin/
    mt
```

You may also place HiggsAgent somewhere other than `tools/higgsagent`, but the instructions below assume that path for clarity.

## Prerequisites

Install these before starting:

- Git
- Python 3.12+
- `uv`
- a shell environment on macOS or Linux
- an OpenRouter API key for hosted model evaluation

Recommended baseline checks:

```bash
python3 --version
uv --version
git --version
```

## Step 1: Create or Prepare the Evaluation Repository

From a new directory:

```bash
mkdir evaluation-repo
cd evaluation-repo
git init
```

Copy or add the Game of Life sample project into the repository.

If you are starting from this HiggsAgent repository as the source of truth, copy:

- `sample-projects/game-of-life/requirements.md`
- `sample-projects/game-of-life/evaluation-instructions.md`
- `sample-projects/game-of-life/tickets/`

For example:

```bash
mkdir -p sample-projects
cp -R /path/to/HiggsAgent/sample-projects/game-of-life sample-projects/
```

After copying, confirm the local board exists:

```bash
find sample-projects/game-of-life/tickets -maxdepth 1 -type f | sort
```

## Step 2: Add HiggsAgent as a Git Submodule

Add HiggsAgent into the evaluation repository as a submodule.

Recommended path:

```bash
git submodule add https://github.com/muonium-ai/HiggsAgent.git tools/higgsagent
git submodule update --init --recursive
```

Why this path:

- it keeps the sample project separate from the framework being evaluated
- it makes it easy to swap HiggsAgent revisions without modifying the sample project definition
- it gives each evaluation run a precise framework commit to compare against

After checkout, initialize the HiggsAgent environment:

```bash
cd tools/higgsagent
uv sync --extra dev
cd ../..
```

If you want the exact reproducible submodule revision recorded in the parent repo, commit the `.gitmodules` file and submodule pointer after setup.

## Step 3: Install MuonTickets From GitHub Binary Releases

For evaluation runs, native MuonTickets binaries are useful because they avoid depending on the Python MuonTickets runtime for routine board operations.

MuonTickets publishes preview GitHub release assets for multiple implementations.

Release asset naming documented upstream:

- `mt-rust-<arch>-<os>.tar.gz`
- `mt-rust-<arch>-windows.zip`
- `mt-zig-<arch>-<os>.tar.gz`
- `mt-zig-<arch>-windows.zip`
- `mt-c-<arch>-<os>.tar.gz`
- `mt-c-<arch>-windows.zip`

For macOS on Apple Silicon, choose the matching `aarch64` macOS release asset.

General install flow:

1. open the MuonTickets GitHub releases page
2. choose the latest release tag
3. download the asset matching your OS and architecture
4. extract the binary into a local `bin/` folder
5. add that folder to your `PATH`

Template commands for macOS or Linux:

```bash
mkdir -p bin
curl -L -o /tmp/mt-release.tar.gz "https://github.com/muonium-ai/muontickets/releases/download/<tag>/mt-rust-<arch>-<os>.tar.gz"
tar -xzf /tmp/mt-release.tar.gz -C bin
chmod +x bin/*
export PATH="$PWD/bin:$PATH"
```

Verify the binary:

```bash
mt --version
```

If you prefer the Python reference CLI instead of a native binary, use:

```bash
uv run python3 tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py --version
```

## Step 4: Validate the Sample Project Ticket Board

Run MuonTickets validation against the sample project board.

Using the binary:

```bash
cd sample-projects/game-of-life
mt validate
```

Using the HiggsAgent-managed Python CLI:

```bash
cd sample-projects/game-of-life
uv run --directory ../../tools/higgsagent python3 ../../tools/higgsagent/tickets/mt/muontickets/muontickets/mt.py validate
```

The board should validate before any agent starts work.

## Step 5: Configure the OpenRouter API Key

HiggsAgent expects the OpenRouter credential through the environment.

Create a local environment file in the evaluation repository root or export the variable directly in your shell.

Minimum environment:

```bash
cat > .env <<'EOF'
OPENROUTER_API_KEY=your_openrouter_key_here
HIGGS_ENV=development
HIGGS_WRITE_MODE=review
EOF
```

Or export it directly:

```bash
export OPENROUTER_API_KEY="your_openrouter_key_here"
export HIGGS_ENV=development
export HIGGS_WRITE_MODE=review
```

Notes:

- `OPENROUTER_API_KEY` is required for hosted model execution through OpenRouter.
- `HIGGS_ENV=development` keeps the run in a development-oriented environment.
- `HIGGS_WRITE_MODE=review` is the safe default for evaluation because it makes review posture explicit.

Do not commit `.env` files containing real credentials.

## Step 6: Choose the Agent Strategy

For evaluation, do not start with many custom agent personas. Keep the run simple so model behavior is easier to compare.

Recommended agent strategy:

### Single-Agent Baseline

Use one coding-capable agent to implement the whole project from the ticket board.

This is best when you want to compare:

- instruction adherence
- completeness
- architectural consistency
- ability to follow dependencies without extra orchestration help

### Coordinator Plus Workers

Use one coordinator agent plus several worker agents if you want to explicitly test parallel execution quality.

Recommended split:

- coordinator agent: owns planning, ticket picking order, and merge discipline
- worker agent A: scaffold and package setup
- worker agent B: core board and simulation logic
- worker agent C: fixtures and parsing
- worker agent D: tests and README once dependencies are ready

### Suggested Owner Labels

If you want ticket ownership to be visible in MuonTickets, use stable owner names such as:

- `coordinator`
- `scaffolder`
- `core-domain-1`
- `core-domain-2`
- `fixtures`
- `io`
- `cli`
- `tests-core`
- `tests-patterns`
- `tests-cli`
- `docs`
- `release`

These owner labels match the suggested ownership hints already written into the Game of Life tickets.

## Step 7: Tell the Agent Exactly What to Read

The agent should always receive these three inputs as its authoritative sources:

1. [requirements.md](requirements.md)
2. the local MuonTickets board under [tickets](tickets)
3. the HiggsAgent submodule under `tools/higgsagent`

The minimum instruction to the agent should explicitly say:

- the Game of Life project is the product to build
- the local sample-project ticket board is the source of task truth
- HiggsAgent is the framework/tooling reference, not the product itself
- the agent must use MuonTickets commands rather than hand-edit ticket lifecycle state
- the agent should preserve dependency order and use parallelism only where tickets allow it

## Recommended Agent Prompt

Use this as the baseline instruction for a model run:

```text
You are implementing the Game of Life sample project in sample-projects/game-of-life.

Read and follow these sources in order:
1. sample-projects/game-of-life/requirements.md
2. sample-projects/game-of-life/tickets/
3. tools/higgsagent documentation and command surface

Constraints:
- Treat the Game of Life sample project as the product to build.
- Treat the local MuonTickets board in sample-projects/game-of-life/tickets as the task system.
- Use MuonTickets commands for claim, comment, status changes, and validation.
- Do not hand-edit ticket lifecycle state.
- Respect ticket dependencies.
- Prefer small, reviewable commits.
- Run tests to verify each completed slice.
- Keep the implementation reproducible with uv and pytest.

Goal:
Build the Game of Life project to satisfy the requirements and complete tickets in dependency order, using parallel work only where the ticket graph permits it.
```

## Step 8: Recommended Execution Workflow

From the evaluation repository root:

### Validate the board

```bash
cd sample-projects/game-of-life
mt validate
cd ../..
```

### Inspect available tickets

```bash
cd sample-projects/game-of-life
mt ls
```

### Claim the initial scaffold ticket

```bash
mt claim T-000002 --owner coordinator
mt show T-000002
```

### After scaffold completion, parallelize safely

Once `T-000002` is done or in review, the following streams can proceed with low overlap:

- board model
- built-in fixtures
- simulation logic after board model
- parsing after board model
- seeded generation after board model

Later, the CLI, tests, and README can branch from those earlier outputs.

### Validate frequently

Use:

```bash
mt validate
```

and the sample project's own tests, once implemented, via the documented `uv run pytest` command.

## Step 9: Compare Models Fairly

To compare model performance, keep these stable across runs:

- the same HiggsAgent submodule commit
- the same Game of Life requirement file
- the same ticket board state at the start of the run
- the same OpenRouter model configuration pattern
- the same stopping condition

Recommended comparison outputs:

- tickets completed
- test pass rate
- number of review loops needed
- command adherence quality
- diff size and project cleanliness
- README/demo quality

## Suggested OpenRouter Model Comparison Strategy

Use one model at a time per clean branch or worktree.

Recommended approach:

1. create a fresh branch or worktree per model
2. reset the Game of Life project to the same initial ticket state
3. run the same agent prompt and operating rules
4. capture resulting commits, test output, and completed tickets
5. compare completeness, correctness, and instruction adherence

This keeps the evaluation focused on agent behavior instead of environmental drift.

## Common Mistakes To Avoid

- pointing the agent at the HiggsAgent repo root instead of the Game of Life sample project
- letting the agent treat `tools/higgsagent` as the product to build
- mixing the sample project's local ticket board with the parent HiggsAgent repository board
- forgetting to export `OPENROUTER_API_KEY`
- comparing models on different ticket states or different framework revisions
- editing ticket lifecycle metadata directly instead of using MuonTickets commands

## Minimal Setup Checklist

- [ ] evaluation repo created
- [ ] Game of Life sample project copied in
- [ ] HiggsAgent added as `tools/higgsagent` submodule
- [ ] HiggsAgent environment synced with `uv`
- [ ] MuonTickets binary installed from GitHub releases
- [ ] `OPENROUTER_API_KEY` exported
- [ ] local Game of Life board validated
- [ ] agent prompt prepared
- [ ] model-specific branch or worktree prepared

## Final Recommendation

For the first comparison run, use a single-agent baseline against the full Game of Life backlog. Once that is stable, repeat the run with a coordinator-plus-workers layout to evaluate parallel ticket execution and coordination quality separately from raw coding quality.