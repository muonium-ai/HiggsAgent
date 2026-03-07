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

## Autonomous Single-Ticket Adoption

HiggsAgent can now act as the code-writing engine for one ready ticket at a time in an adopted repository.

Recommended setup for a separate repository:

1. Add HiggsAgent to the repository and sync the `uv` environment.
2. Install or vendor MuonTickets under `tickets/mt/muontickets`.
3. Create repository-specific guardrails and write-policy JSON files.
4. Create a requirements or project-context file that gives the runtime enough scope for one ticket.
5. Validate the board with `uv run higgs-agent validate tickets`.
6. Run `uv run higgs-agent run autonomous-ticket ...` with explicit validation commands.
7. Review the changed files, `.higgs/local` telemetry, and any review-handoff artifact before merging.

Current limits matter:

- HiggsAgent completes one dependency-unblocked ready ticket per invocation.
- The runtime currently materializes bounded directory creation and full-file writes from structured OpenRouter JSON.
- Review remains mandatory after `needs_review`; HiggsAgent does not auto-complete the ticket to `done`.
- Project-wide autonomous completion remains a later phase.

## For New Repositories

If you are starting from scratch rather than adopting HiggsAgent in an existing codebase, begin with [new-project-quickstart.md](new-project-quickstart.md). That guide covers the initial Git, `uv`, directory layout, MuonTickets installation, and first-commit flow that this overview intentionally does not repeat in detail.

## Normative Sources

- [../architecture.md](../architecture.md)
- [../ticket-semantics.md](../ticket-semantics.md)
- [../runtime-tooling.md](../runtime-tooling.md)

## Update When

- integration flow changes
- required runtime or tooling prerequisites change
- autonomous execution boundaries change