# Repository Structure

## Purpose

This document locks the initial repository layout and ownership boundaries for HiggsAgent. The goal is to reduce merge contention, keep product runtime code separate from auxiliary tooling, and make future swarm execution safer.

## Top-Level Layout

- `src/` contains PHP product runtime code.
- `bin/` contains CLI entrypoints for the product runtime.
- `config/` contains portable runtime and policy configuration examples.
- `schemas/` contains language-neutral contracts shared across phases and future ports.
- `tests/` contains PHP test suites and fixtures.
- `docs/` contains normative contracts and public-facing guidance.
- `tickets/` contains MuonTickets workflow state and is not part of the product runtime.
- `var/` contains local runtime state only and must not be committed.

## Source Packages

- `src/Application/` owns orchestration flow.
- `src/Tickets/` owns ticket loading and eligibility checks.
- `src/Routing/` owns normalized routing inputs and deterministic selection.
- `src/Providers/Contract/` owns provider interfaces and shared DTOs.
- `src/Providers/Hosted/` owns hosted-provider adapters.
- `src/Guardrails/` owns budgets, retries, and policy enforcement.
- `src/Validation/` owns output validation and repository write decisions.
- `src/Events/` owns execution event emission and export boundaries.
- `src/Support/` owns low-level helpers only.

## Tests

- `tests/Unit/` for isolated package behavior.
- `tests/Integration/` for fixture-backed cross-package flows.
- `tests/Fixtures/` for tickets, events, policy files, and provider samples.
- `tests/Contract/` for schema and configuration validation.
- `tests/Concurrency/` for policy and shared-surface smoke coverage.

## Ownership Boundaries

- `Application` may depend on routing, providers, validation, guardrails, and events.
- `Routing` must not depend on provider implementations.
- `Providers/Contract` is a shared hotspot and should stabilize before provider adapter parallelism increases.
- `Validation` and `Guardrails` remain separate so write decisions do not leak into provider code.
- `schemas/`, `config/`, and shared control-plane files are protected surfaces.

## High Merge-Risk Hotspots

These paths should be tightly owned or serialized:

- `composer.json`
- `Makefile`
- `schemas/`
- `config/`
- `src/Routing/`
- `src/Providers/Contract/`
- `src/Validation/`
- `src/Guardrails/`
- `src/Events/`

## Swarm-Safe Zones

These areas are good parallel targets once shared contracts are stable:

- `src/Providers/Hosted/`
- package-local unit tests
- subsystem docs
- fixture additions with clear ownership

## Rules

- Do not add new top-level runtime trees without updating this contract.
- Do not place product runtime logic under `tickets/` or Python-only tooling paths.
- Keep portable contracts in `schemas/` and `config/`, not embedded in PHP-only structures.