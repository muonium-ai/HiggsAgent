# HiggsAgent

HiggsAgent is a Git-native autonomous agent dispatcher that routes work based on structured ticket semantics and records execution decisions in a white-box, inspectable way.

## Status

The repository is currently in Phase 0 foundation work. The dispatcher runtime is not implemented yet; the current focus is locking the runtime, schema, observability, and safety contracts that later phases depend on.

## Runtime Model

- Product runtime: PHP 8.3 CLI
- Product dependency management: Composer
- Auxiliary tooling: Python 3.12+ managed with `uv`
- Ticket workflow: MuonTickets under `tickets/mt/muontickets`
- Top-level task entrypoint: `make`

`uv` is used for ticket automation and auxiliary repository tooling. It is not the product runtime for HiggsAgent itself.

## Quickstart

1. Install PHP 8.3+, Composer, Python 3.12+, and `uv`.
2. Initialize MuonTickets if needed:

	```bash
	uv run python3 tickets/mt/muontickets/muontickets/mt.py validate
	```

3. Review the runtime contract in [docs/runtime-tooling.md](docs/runtime-tooling.md).
4. Use `make help` for the documented task surface.

## Repository Guides

- [docs/architecture.md](docs/architecture.md)
- [docs/runtime-tooling.md](docs/runtime-tooling.md)
- [docs/repository-structure.md](docs/repository-structure.md)
- [docs/todo.md](docs/todo.md)

## Ticket Workflow

The backlog is tracked with MuonTickets. Use the submodule CLI from the repository root:

```bash
uv run python3 tickets/mt/muontickets/muontickets/mt.py ls
uv run python3 tickets/mt/muontickets/muontickets/mt.py show T-000003
uv run python3 tickets/mt/muontickets/muontickets/mt.py validate
```
