# Runtime and Tooling Contract

## Objective

This document defines the supported runtime and tooling model for HiggsAgent during the foundation and Phase 1 work.

## Contract

- Product runtime: Python 3.12+
- Product package, environment, and execution manager: `uv`
- Ticket tooling runtime: Python 3.12+
- Ticket tooling manager: `uv`
- Task runner: `make`

## Boundary Rules

- Product logic belongs in Python.
- Ticket lifecycle operations remain in MuonTickets and continue to run through Python.
- Portable assets such as schemas and configuration should be language-neutral wherever possible.
- Future ports to Rust, Go, or Zig must be able to reuse schemas and config without rewriting contracts.

## Why This Split Exists

The repository contract is that HiggsAgent itself is implemented in Python and managed with `uv`.

This avoids three common problems:

1. Splitting product logic across two runtime stacks before the first implementation exists.
2. Requiring contributors to guess which tool is the authoritative environment manager.
3. Making later ports depend on an unnecessary transitional runtime.

## Supported Contributor Surface

Contributors should rely on:

- `uv sync` for environment and dependency installation.
- `uv run ...` for project commands.
- `uv run python3 tickets/mt/muontickets/muontickets/mt.py ...` for ticket board operations.
- `make` for top-level project commands that wrap the `uv`-managed command surface.

## Initial Supported Environment

- Python 3.12+
- `uv`
- macOS and Linux for local contributor workflows

## Deferred Decisions

These are intentionally not committed yet:

- Docker-based development workflow
- Standalone binary packaging
- Local model runtime packaging
- Production deployment topology

## CI Expectations

The project should maintain two distinct CI lanes once CI is added:

1. Python product lane for HiggsAgent runtime validation.
2. Python tooling lane for ticket tooling and auxiliary repository checks.

The two lanes should stay logically independent even though both use Python, so product code does not become tightly coupled to ticket automation internals.

## Required Root Files

This contract expects the following root-level files to exist:

- `pyproject.toml`
- `Makefile`
- `.env.example`
- `README.md`

## Risks

- If repository automation starts carrying product logic that bypasses the package root, the runtime boundary will erode and later phases will become harder to port.
- If the project adds unmanaged scripts outside `uv`, contributor reproducibility will degrade quickly.