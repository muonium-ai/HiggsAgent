# Guardrails and Artifacts

## Audience

Operators and maintainers reviewing execution safety.

## Purpose

Provide a concise operational summary of budgets, protected surfaces, local-only artifacts, and secret handling.

## Summary

- Token, cost, timeout, tool-call, and retry budgets are enforced through guardrail policy.
- Protected surfaces require human review.
- Raw prompts, raw responses, provider payloads, and secret-bearing output stay local by default.
- Sanitized summaries may be retained, but raw telemetry should not be committed.

## Normative Sources

- [../safety-model.md](../safety-model.md)
- [../secret-handling.md](../secret-handling.md)
- [../storage-boundaries-and-retention.md](../storage-boundaries-and-retention.md)

## Update When

- budget defaults change
- retention or redaction rules change
- protected-path policy changes