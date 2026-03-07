# Repository Requirements

## Audience

Teams preparing a repository for HiggsAgent.

## Purpose

State the repository-level assumptions that HiggsAgent depends on.

## Requirements

- Tickets must follow MuonTickets workflow rules.
- The repository must provide a documented `uv`-based setup path.
- The repository should expose a small top-level command surface for sync, validation, tests, and linting.
- Higgs routing fields must be present and valid for executable work.
- Protected surfaces and write policy must be respected.
- Local execution artifacts must remain out of version control by default.
- Runtime code, tests, docs, configuration, and ticket state must have clearly separated locations.

## Minimum Layout

The following layout is the expected baseline:

- `src/` for runtime code
- `tests/` for automated checks
- `docs/` for contracts and user guidance
- `config/` for guardrails and write-policy configuration
- `tickets/` for MuonTickets state
- `var/` for local-only runtime artifacts

## Minimum Workflow Commands

The repository should document commands equivalent to these:

- `uv sync --extra dev`
- `uv run higgs-agent validate tickets`
- `uv run pytest`
- `uv run ruff check src tests`

If these commands are wrapped in `make`, the wrappers should remain thin and visible.

## Normative Sources

- [../ticket-semantics.md](../ticket-semantics.md)
- [../routing-normalization.md](../routing-normalization.md)
- [../storage-boundaries-and-retention.md](../storage-boundaries-and-retention.md)

## Update When

- ticket field requirements change
- repository write policy changes
- artifact retention rules change