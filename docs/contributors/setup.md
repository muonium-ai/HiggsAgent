# Contributor Setup

## Audience

Contributors preparing a local development environment.

## Purpose

Define the supported setup path for HiggsAgent under the Python-plus-uv contract.

## Supported Toolchain

- Python 3.12+
- `uv`
- Git

## Setup

```bash
uv sync --extra dev
uv run higgs-agent --help
make tickets-validate
make lint
```

## Normative Sources

- [../runtime-tooling.md](../runtime-tooling.md)
- [../testing-strategy.md](../testing-strategy.md)

## Update When

- Python or `uv` requirements change
- local validation commands change