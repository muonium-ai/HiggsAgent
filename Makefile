.PHONY: help sync tickets-validate test lint format

help:
	@printf '%s\n' \
	  'Available targets:' \
	  '  make sync              Sync the uv-managed project environment' \
	  '  make tickets-validate  Validate the MuonTickets board' \
	  '  make test              Run the Python test suite' \
	  '  make lint              Run Ruff checks' \
	  '  make format            Run Ruff formatting'

sync:
	uv sync --extra dev

tickets-validate:
	uv run python3 tickets/mt/muontickets/muontickets/mt.py validate

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .