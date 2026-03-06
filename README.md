# HiggsAgent

HiggsAgent is a Git-native autonomous agent dispatcher that routes work based on structured ticket semantics and records execution decisions in a white-box, inspectable way.

## Status

The repository is currently in Phase 0 foundation work. The dispatcher runtime is not implemented yet; the current focus is locking the runtime, schema, observability, and safety contracts that later phases depend on.

## Runtime Model

- Product runtime: Python 3.12+
- Product dependency and environment management: `uv`
- Ticket and auxiliary tooling: Python 3.12+ managed with `uv`
- Ticket workflow: MuonTickets under `tickets/mt/muontickets`
- Top-level task entrypoint: `make`

`uv` is the package, environment, and execution entrypoint for HiggsAgent itself and for the repository's Python tooling.

## Quickstart

1. Install Python 3.12+ and `uv`.
2. Sync the workspace environment:

	```bash
	uv sync --extra dev
	```

3. Validate MuonTickets if needed:

	```bash
	uv run python3 tickets/mt/muontickets/muontickets/mt.py validate
	```

4. Review the runtime contract in [docs/runtime-tooling.md](docs/runtime-tooling.md).
5. Use `make help` for the documented task surface.

## Repository Guides

- [docs/README.md](docs/README.md)
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
