# Repository Structure

## Purpose

This document locks the initial repository layout and ownership boundaries for HiggsAgent. The goal is to reduce merge contention, keep Python product runtime code separate from ticket tooling, and make future swarm execution safer.

## Top-Level Layout

- `src/` contains Python product runtime code.
- `src/higgs_agent/` is the Python package root for HiggsAgent.
- `bin/` contains optional CLI wrappers.
- `config/` contains portable runtime and policy configuration examples.
- `schemas/` contains language-neutral contracts shared across phases and future ports.
- `tests/` contains Python test suites and fixtures.
- `docs/` contains normative contracts and public-facing guidance.
- `tickets/` contains MuonTickets workflow state and is not part of the product runtime.
- `var/` contains local runtime state only and must not be committed.

## Source Packages

- `src/higgs_agent/application/` owns orchestration flow.
- `src/higgs_agent/tickets/` owns ticket loading and eligibility checks.
- `src/higgs_agent/routing/` owns normalized routing inputs and deterministic selection.
- `src/higgs_agent/providers/contract/` owns provider interfaces and shared models.
- `src/higgs_agent/providers/hosted/` owns hosted-provider adapters.
- `src/higgs_agent/guardrails/` owns budgets, retries, and policy enforcement.
- `src/higgs_agent/validation/` owns output validation and repository write decisions.
- `src/higgs_agent/events/` owns execution event emission and export boundaries.
- `src/higgs_agent/support/` owns low-level helpers only.

## Tests

- `tests/Unit/` for isolated package behavior.
- `tests/Integration/` for fixture-backed cross-package flows.
- `tests/Fixtures/` for tickets, events, policy files, and provider samples.
- `tests/Contract/` for schema and configuration validation.
- `tests/Concurrency/` for policy and shared-surface smoke coverage.

## Ownership Boundaries

- `application` may depend on routing, providers, validation, guardrails, and events.
- `routing` must not depend on provider implementations.
- `providers/contract` is a shared hotspot and should stabilize before provider adapter parallelism increases.
- `validation` and `guardrails` remain separate so write decisions do not leak into provider code.
- `schemas/`, `config/`, and shared control-plane files are protected surfaces.

## High Merge-Risk Hotspots

These paths should be tightly owned or serialized:

- `pyproject.toml`
- `Makefile`
- `schemas/`
- `config/`
- `src/higgs_agent/routing/`
- `src/higgs_agent/providers/contract/`
- `src/higgs_agent/validation/`
- `src/higgs_agent/guardrails/`
- `src/higgs_agent/events/`

## Swarm-Safe Zones

These areas are good parallel targets once shared contracts are stable:

- `src/higgs_agent/providers/hosted/`
- package-local unit tests
- subsystem docs
- fixture additions with clear ownership

## Rules

- Do not add new top-level runtime trees without updating this contract.
- Do not place product runtime logic under `tickets/` or Python-only tooling paths.
- Keep portable contracts in `schemas/` and `config/`, not embedded in package-only Python modules.