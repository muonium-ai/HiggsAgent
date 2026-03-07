# HiggsAgent

HiggsAgent is a Git-native autonomous agent dispatcher that routes work based on structured ticket semantics and records execution decisions in a white-box, inspectable way.

## Status

The repository is currently through Phase 5 benchmarking foundations. The runtime now includes deterministic hosted and local route selection, bounded fallback behavior, normalized observability, analytics reporting, adaptive telemetry ingestion, explainable adaptive scoring surfaces, curated benchmark workloads, comparable benchmark execution, benchmark ranking outputs, and write-gate validation.

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

3. Check the installed HiggsAgent CLI surface:

	```bash
	uv run higgs-agent --help
	```

4. Validate MuonTickets if needed:

	```bash
	uv run higgs-agent validate tickets
	```

5. Review the runtime contract in [docs/runtime-tooling.md](docs/runtime-tooling.md).
6. If you want to use HiggsAgent patterns in a fresh repository, start with [docs/adopters/new-project-quickstart.md](docs/adopters/new-project-quickstart.md).
7. Review the benchmark methodology contract in [docs/phase-5-benchmarking-mode.md](docs/phase-5-benchmarking-mode.md) and the operator, contributor, and adopter guides under [docs/operators](docs/operators), [docs/contributors](docs/contributors), and [docs/adopters](docs/adopters).
8. Use `make help` for the documented task surface.

## Repository Guides

- [docs/README.md](docs/README.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/adopters/new-project-quickstart.md](docs/adopters/new-project-quickstart.md)
- [docs/phase-1-dispatcher-mvp.md](docs/phase-1-dispatcher-mvp.md)
- [docs/runtime-tooling.md](docs/runtime-tooling.md)
- [docs/repository-structure.md](docs/repository-structure.md)
- [docs/todo.md](docs/todo.md)

## Ticket Workflow

The backlog is tracked with MuonTickets. Use the submodule CLI from the repository root:

```bash
uv run python3 tickets/mt/muontickets/muontickets/mt.py ls
uv run python3 tickets/mt/muontickets/muontickets/mt.py show T-000003
uv run higgs-agent validate tickets
```
