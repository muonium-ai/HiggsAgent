.PHONY: help tickets-validate setup-php

help:
	@printf '%s\n' \
	  'Available targets:' \
	  '  make tickets-validate  Validate the MuonTickets board' \
	  '  make setup-php         Install Composer dependencies when present'

tickets-validate:
	uv run python3 tickets/mt/muontickets/muontickets/mt.py validate

setup-php:
	composer install