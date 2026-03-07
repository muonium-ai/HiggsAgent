# New Project Quickstart

## Audience

Teams using HiggsAgent as the reference model for a brand-new repository.

## Purpose

Provide a concrete bootstrap path for a new project that wants HiggsAgent-style repository structure, ticket workflow, and safety boundaries.

## Scope

This guide is about creating a repository that adopts HiggsAgent's workflow and contracts.

It is not a one-command scaffold. HiggsAgent provides reference architecture, contracts, project patterns, and a single-ticket autonomous runtime rather than a packaged full-project `init` or project-completion command.

## Before You Start

- Install Python 3.12+.
- Install `uv`.
- Install Git.
- Decide your Python package name.
- Decide whether your repository will allow automated writes immediately or only after manual review.

## Recommended Bootstrap Flow

If you are starting from a shipped sample project, prefer the first-party bootstrap command instead of reconstructing the repository layout by hand:

```bash
higgs-agent bootstrap sample-project ../my-evaluation-repo --sample-project game-of-life
```

The command initializes the target Git repository, copies the sample-project assets, adds `tools/higgsagent` as a submodule, creates the local `.higgs/` directories, and validates the copied ticket board.

Use the manual flow below when you are creating a fully custom repository instead of one of the shipped sample-project layouts.

1. Create the repository root and initialize Git.

   ```bash
   mkdir my-project
   cd my-project
   git init
   ```

2. Initialize a `uv`-managed Python project and sync the environment.

   ```bash
   uv init
   uv sync --extra dev
   ```

3. Create the baseline HiggsAgent-style layout.

   ```bash
   mkdir -p src/my_project tests docs config schemas var
   mkdir -p tickets/mt
   ```

4. Install MuonTickets as a submodule and initialize the board.

   ```bash
   git submodule add https://github.com/muonium-ai/muontickets.git tickets/mt/muontickets
   git submodule update --init --recursive
   uv run python3 tickets/mt/muontickets/muontickets/mt.py init
   uv run higgs-agent validate tickets
   ```

5. Add the first project-local control files.

   Minimum recommended files:

   - `README.md`
   - `Makefile`
   - `docs/architecture.md`
   - `config/guardrails.json` or `config/guardrails.example.json`
   - `config/write-policy.json` or `config/write-policy.example.json`
   - `tickets/ticket.template`

6. Create your first tickets from the initialized board.

   ```bash
   uv run python3 tickets/mt/muontickets/muontickets/mt.py new "Define repository contracts" --type spec --priority p0
   uv run python3 tickets/mt/muontickets/muontickets/mt.py new "Implement first runtime slice" --type code --priority p1
   ```

7. Commit the bootstrap state.

   ```bash
   git add .
   git commit -m "Bootstrap project with HiggsAgent-style workflow"
   ```

## Minimal Makefile Surface

At minimum, expose the same top-level workflow categories HiggsAgent uses:

```make
.PHONY: sync tickets-validate test lint

sync:
	uv sync --extra dev

tickets-validate:
   uv run higgs-agent validate tickets

test:
	uv run pytest

lint:
	uv run ruff check src tests
```

This keeps contributor commands obvious and prevents ticket validation from becoming tribal knowledge.

## Minimum Repository Expectations

Your new repository should preserve these assumptions if you want HiggsAgent-compatible workflow behavior:

- Product logic lives under `src/`.
- Tests live under `tests/`.
- Docs and contracts live under `docs/`.
- Runtime configuration and policy live under `config/`.
- Ticket state is managed through `tickets/` and MuonTickets commands, not manual metadata edits for lifecycle actions.
- Local runtime state lives under `var/` and should not be committed.

## Copy First, Customize Second

When adopting HiggsAgent patterns, start by copying the workflow shape before customizing semantics.

Recommended order:

1. Copy the repository layout and command surface.
2. Install and validate MuonTickets.
3. Define your write policy and guardrails.
4. Define your project-specific ticket frontmatter extensions.
5. Only then add provider integrations, execution logic, or automation.

After the repository boundaries are explicit, you can use `uv run higgs-agent run autonomous-ticket ...` as the code-writing engine for one ready ticket at a time.

This order reduces the risk of building execution features before the repository boundaries are explicit.

## Common Failure Modes

- Running MuonTickets from the wrong path instead of using `higgs-agent validate tickets` or the documented `tickets/mt/muontickets/muontickets/mt.py` path.
- Treating ticket lifecycle files as hand-edited state for `claim`, `done`, `archive`, or `comment` instead of using the CLI.
- Adding automation before defining protected paths and write policy.
- Mixing multiple environment managers instead of making `uv` the single documented entrypoint.
- Treating `var/` as committed state.

## Read Next

- [integration-overview.md](integration-overview.md)
- [repository-requirements.md](repository-requirements.md)
- [../runtime-tooling.md](../runtime-tooling.md)
- [../repository-structure.md](../repository-structure.md)
- [../ticket-semantics.md](../ticket-semantics.md)

## Normative Sources

- [../runtime-tooling.md](../runtime-tooling.md)
- [../repository-structure.md](../repository-structure.md)
- [../safety-model.md](../safety-model.md)
- [../ticket-semantics.md](../ticket-semantics.md)

## Update When

- the supported bootstrap flow changes
- the MuonTickets installation path changes
- the required repository layout changes
- the minimum command surface changes