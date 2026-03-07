# Integration Overview

## Audience

Repository owners evaluating HiggsAgent adoption.

## Purpose

Describe the high-level integration shape without assuming later runtime phases already exist.

## Recommended Adoption Order

1. Bootstrap the repository and environment.
2. Install MuonTickets and validate the board.
3. Define project contracts, write policy, and guardrails.
4. Define ticket semantics and routing inputs.
5. Add execution or automation only after the repository boundaries are explicit.

## Current Expectations

- Use MuonTickets for work coordination.
- Maintain Higgs-specific ticket semantics in frontmatter.
- Keep contracts and configuration in version control.
- Apply guardrails before allowing automated repository writes.

## For New Repositories

If you are starting from scratch rather than adopting HiggsAgent in an existing codebase, begin with [new-project-quickstart.md](new-project-quickstart.md). That guide covers the initial Git, `uv`, directory layout, MuonTickets installation, and first-commit flow that this overview intentionally does not repeat in detail.

## Normative Sources

- [../architecture.md](../architecture.md)
- [../ticket-semantics.md](../ticket-semantics.md)
- [../runtime-tooling.md](../runtime-tooling.md)

## Update When

- integration flow changes
- required runtime or tooling prerequisites change