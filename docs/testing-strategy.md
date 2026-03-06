# Testing Strategy

## Purpose

This document defines the Phase 0 testing baseline and CI matrix for HiggsAgent under the Python-plus-uv runtime contract.

## Test Pyramid

- Contract tests validate schemas, config examples, and routing-policy invariants.
- Unit tests validate package-local behavior and layout assumptions.
- Integration tests validate fixture-backed cross-contract flows without network access.
- Concurrency tests remain smoke-only until shared write and claim logic exists.

## Current Priorities

### Blocking

- `make sync`
- `make lint`
- `make contract-test`
- `uv run pytest tests/Unit tests/Integration`
- `make tickets-validate`

### Smoke-only

- `make smoke-test`
- macOS runs
- Python 3.13 compatibility runs

## CI Lanes

### Product CI

- Purpose: validate the Python runtime surface for HiggsAgent.
- Platform: `ubuntu-latest`
- Python: `3.12`
- Blocking on pull requests and pushes to `main`

### Tooling CI

- Purpose: validate ticket tooling and board integrity.
- Platform: `ubuntu-latest`
- Python: `3.12`
- Blocking on pull requests and pushes to `main`

### Smoke CI

- Purpose: low-cost compatibility and policy smoke coverage.
- Platforms: `ubuntu-latest`, `macos-latest`
- Python: `3.12`, `3.13`
- Non-blocking, scheduled and manually triggered

## Test Ownership Rules

- Schema and config changes must ship with contract test updates.
- Package or runtime changes must ship with unit tests and at least one integration path when behavior crosses package boundaries.
- Protected-surface and write-policy changes must keep smoke coverage updated.
- Hosted-provider or network-dependent behavior must stay out of blocking CI until explicit stubbing exists.