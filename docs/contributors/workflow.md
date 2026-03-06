# Contributor Workflow

## Audience

Contributors making changes to HiggsAgent.

## Purpose

Explain how contract work, implementation work, and ticket workflow fit together.

## Workflow Rules

- Use MuonTickets as the source of task coordination.
- Keep changes scoped to the claimed ticket.
- Update related docs and tests in the same change when contracts move.
- Treat `schemas/`, `config/`, `pyproject.toml`, `Makefile`, and guarded control-plane files as high-coordination surfaces.

## Validation Commands

```bash
make lint
make contract-test
uv run pytest tests/Unit tests/Integration
make smoke-test
make tickets-validate
```

## Normative Sources

- [../repository-structure.md](../repository-structure.md)
- [../safety-model.md](../safety-model.md)
- [../documentation-policy.md](../documentation-policy.md)

## Update When

- validation requirements change
- protected surfaces or ticket workflow constraints change