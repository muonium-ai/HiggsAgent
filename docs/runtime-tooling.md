# Runtime and Tooling Contract

## Objective

This document defines the supported runtime and tooling model for HiggsAgent through the Phase 3 hybrid execution milestone.

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
- Local model execution must fit behind the existing Python provider boundary rather than introducing a second product runtime stack.

## Phase 3 Hybrid Runtime

Phase 3 adds an optional local execution path without changing the repository runtime contract.

- HiggsAgent remains a Python application managed through `uv`.
- Hosted and local execution share the same normalized provider result, event, and attempt-summary contracts.
- Local execution is optional and only enabled when a local transport is explicitly configured by the runtime.
- The repository does not yet package or install a production local model runtime for contributors.

## Local Execution Prerequisites

The current Phase 3 local path assumes all of the following:

- Python 3.12+ and `uv` remain the only supported product toolchain.
- A compatible local model runtime or daemon is installed and managed outside the repository.
- The local runtime can satisfy the provider transport boundary expected by HiggsAgent.
- Operators understand that some local usage fields may be partial, especially exact billing data.

The current repository does not define a bundled Ollama, llama.cpp, vLLM, or GPU packaging workflow. That remains a later operational concern.

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

Phase 3 local execution should be treated as supported for controlled contributor and operator workflows on macOS and Linux only. Windows-specific local runtime support remains undocumented in this phase.

## Deferred Decisions

These are intentionally not committed yet:

- Docker-based development workflow
- Standalone binary packaging
- Local model runtime packaging
- Production deployment topology
- Automatic local-runtime discovery
- Hosted-to-local fallback policy

## Hybrid Operational Limits

- `higgs_execution_target=local` requires an explicit local runtime and currently supports toolless requests only.
- `higgs_execution_target=auto` may prefer local execution only for deterministic low-risk cases defined by the routing policy.
- Bounded fallback currently applies from failed auto-local attempts to hosted execution.
- Explicit local requests do not silently fall back to hosted execution.
- Local execution may omit exact `cost_usd` values when the local runtime cannot provide precise billing data.

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
- If local runtime setup is treated as implicit or self-discovering, operators may misread blocked local routes as product defects instead of configuration gaps.
- If partial local metrics are presented as exact hosted-style billing data, operator trust in analytics output will erode.