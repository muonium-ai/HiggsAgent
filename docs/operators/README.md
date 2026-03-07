# Operator Guide

## Audience

Operators responsible for running or reviewing HiggsAgent executions.

## Purpose

This guide routes operators to runtime, guardrail, observability, and artifact-handling expectations.

The supported installed operator surface lives under `uv run higgs-agent ...`.

## Read Next

- [runbook.md](runbook.md)
- [autonomous-ticket.md](autonomous-ticket.md)
- [turnkey-project.md](turnkey-project.md)
- [dispatcher.md](dispatcher.md)
- [adaptive-dispatch.md](adaptive-dispatch.md)
- [benchmarking.md](benchmarking.md)
- [guardrails-and-artifacts.md](guardrails-and-artifacts.md)
- [analytics.md](analytics.md)
- [hybrid-execution.md](hybrid-execution.md)
- [../safety-model.md](../safety-model.md)

## Normative Sources

- [../safety-model.md](../safety-model.md)
- [../observability-contract.md](../observability-contract.md)
- [../secret-handling.md](../secret-handling.md)

## Update When

- write policy changes
- guardrail defaults change
- retention or redaction rules change
- hosted versus local execution behavior changes
- autonomous single-ticket execution behavior or operator inputs change
- turnkey project-build behavior, stop conditions, or review flow change
- adaptive scoring behavior, review expectations, or rollout guidance changes
- benchmarking methodology, interpretation limits, or public review expectations change
- dispatcher execution or review workflow changes