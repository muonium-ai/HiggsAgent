# Runtime and Tooling Contract

## Objective

This document defines the supported runtime and tooling model for HiggsAgent during the foundation and Phase 1 work.

## Contract

- Product runtime: PHP 8.3 CLI
- Product package manager: Composer
- Auxiliary tooling runtime: Python 3.12+
- Auxiliary tooling manager: `uv`
- Task runner: `make`

## Boundary Rules

- Product logic belongs in PHP.
- Ticket lifecycle operations remain in MuonTickets and continue to run through Python.
- Portable assets such as schemas and configuration should be language-neutral wherever possible.
- Future ports to Rust, Go, or Zig must be able to reuse schemas and config without rewriting contracts.

## Why This Split Exists

The PRD states that HiggsAgent will start in PHP while the repository already uses `uv` for MuonTickets. The cleanest contract is to keep `uv` as auxiliary tooling only and treat PHP plus Composer as the product runtime surface.

This avoids three common problems:

1. Blurring product runtime logic with repository automation.
2. Requiring contributors to guess which tool owns which workflows.
3. Making later runtime ports depend on Python-specific behavior.

## Supported Contributor Surface

Contributors should rely on:

- `composer` for PHP dependency installation and PHP-centric scripts.
- `uv run python3 tickets/mt/muontickets/muontickets/mt.py ...` for ticket board operations.
- `make` for top-level project commands that wrap both PHP and Python tooling.

## Initial Supported Environment

- PHP 8.3+
- Composer 2+
- Python 3.12+
- `uv`
- macOS and Linux for local contributor workflows

## Deferred Decisions

These are intentionally not committed yet:

- PHAR packaging
- Docker-based development workflow
- Global installer or Homebrew formula
- Local model runtime packaging
- Production deployment topology

## CI Expectations

The project should maintain two distinct CI lanes once CI is added:

1. PHP lane for product runtime validation.
2. Python lane for ticket tooling and auxiliary repository checks.

The two lanes should stay independent so later runtime changes do not unintentionally couple product code to repository automation.

## Required Root Files

This contract expects the following root-level files to exist:

- `composer.json`
- `Makefile`
- `.env.example`
- `README.md`

## Risks

- If the project later abandons PHP earlier than expected, the Composer-based contract will need to be revised.
- If repository automation starts carrying product logic, the runtime boundary will erode and later phases will become harder to port.