# Documentation Policy

## Goal

Keep the public documentation set aligned with the normative contracts while giving contributors, operators, and adopters clear entrypoints.

## Source of Truth

- Root-level contract documents in `docs/` are normative.
- Audience guides summarize and link to those contracts.
- If guidance and contracts diverge, the contract document wins until the guidance is corrected.

## Audience Sets

- Contributors: setup, workflow, local validation, and development boundaries.
- Operators: runbooks, guardrails, review handoff, and artifact policy.
- Adopters: integration expectations, repository requirements, and rollout constraints.

## Update Rules

Update the audience guides in the same change whenever any of these move:

- runtime/tooling contract
- repository structure
- ticket semantics
- observability schema or retention rules
- guardrail or secret-handling policy
- validation and write policy

## Ownership

- Architecture and runtime contracts: core maintainers.
- Contributor docs: runtime and tooling maintainers.
- Operator docs: guardrail and observability maintainers.
- Adopter docs: architecture and ticket-semantics maintainers.

## Minimal Metadata Convention

Audience-facing docs should include:

- intended audience
- purpose
- normative sources
- when the doc must be updated