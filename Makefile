.PHONY: help sync tickets-validate test contract-test smoke-test lint format

help:
	@printf '%s\n' \
	  'Available targets:' \
	  '  make sync              Sync the uv-managed project environment' \
	  '  make tickets-validate  Validate the MuonTickets board' \
	  '  make test              Run the Python test suite' \
	  '  make contract-test     Run contract validation tests' \
	  '  make smoke-test        Run smoke-only policy tests' \
	  '  make lint              Run Ruff checks' \
	  '  make format            Run Ruff formatting'

sync:
	uv sync --extra dev

tickets-validate:
	uv run python3 tickets/mt/muontickets/muontickets/mt.py validate

test:
	uv run pytest

contract-test:
	uv run pytest tests/Contract

smoke-test:
	uv run pytest tests/Concurrency

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests