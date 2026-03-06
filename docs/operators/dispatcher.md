# Dispatcher Operations

## Audience

Operators and reviewers working with the deterministic dispatcher pipeline.

## Purpose

Describe the implemented dispatcher flow from ticket scan through validation, the current execution surface, and the operator-visible safety boundaries.

## What Phase 1 Actually Delivered

Phase 1 established the first usable dispatcher pipeline for HiggsAgent.

The implemented flow is:

1. scan the ticket tree for parseable tickets
2. select the next eligible `ready` ticket using workflow-only ordering
3. normalize ticket semantics into routing inputs
4. choose an explainable execution route
5. execute through the provider boundary
6. validate proposed writes before any repository mutation
7. emit execution events and an attempt summary

This remains the baseline execution model even though later phases added analytics and hybrid hosted or local routing.

## Current Runtime Surface

The dispatcher is currently a library-first runtime surface, not a public dispatch CLI.

- Analytics reporting is exposed through the `higgs-agent analytics report` command.
- Dispatcher execution itself is exposed through `higgs_agent.application.dispatch_next_ready_ticket`.
- Integration tests show the supported orchestration boundary for the current runtime.

Operators should not assume there is a stable top-level `dispatch` command yet. The current product contract is still centered on explicit Python surfaces and validated configuration files.

## Configuration Inputs

The dispatcher currently depends on two repository configuration files:

- `config/guardrails.example.json`
- `config/write-policy.example.json`

These control:

- prompt, completion, timeout, retry, tool-call, and cost limits
- local retention defaults for raw versus normalized artifacts
- protected-path handling and handoff requirements
- whether human review is required for policy-sensitive changes

Operators should treat these files as control-plane inputs. Changes to either file require careful review.

## Ticket Requirements

For a ticket to be dispatchable it must be:

- parseable as a MuonTickets record
- in `ready` status
- unblocked by unfinished dependencies
- compatible with the Higgs semantic normalization rules

Key Higgs fields that affect dispatch behavior:

- `type`
- `priority`
- `higgs_platform`
- `higgs_complexity`
- `higgs_execution_target`
- `higgs_tool_profile`

The dispatcher uses these fields to build a deterministic route rationale rather than a hidden score.

## Execution Outcomes Operators Should Expect

The current dispatcher surface returns a structured outcome with:

- the selected ticket
- normalized semantics
- the route decision and rationale
- the normalized execution result
- the write-gate decision

Write-gate outcomes are intentionally narrow:

- `accepted`: the proposed change set is within policy
- `handoff_required`: a human must review the result before repository mutation
- `rejected`: execution did not produce an acceptable result for repository write consideration

Protected paths, policy violations, and secret-suspect output should be expected to produce handoff or rejection rather than silent mutation.

## Observability Boundary

Every dispatcher attempt should remain inspectable through schema-aligned records.

Operators should expect:

- execution lifecycle events
- attempt summaries with final result, provider, model, retries, tool-call count, and usage where available
- route rationale and fallback metadata when hybrid execution is active

Raw prompts, raw responses, and provider payloads remain local-only and should not be treated as normal review artifacts.

## Phase Boundaries

Keep these distinctions clear when reading the code or operating the system:

- Phase 1: deterministic scan, classify, route, execute, validate, and observe
- Phase 2: analytics aggregation and reporting over normalized outputs
- Phase 3: optional local execution and bounded fallback on top of the same dispatcher shape
- Later phases: adaptive dispatch and benchmarking are not implemented yet

Operators should use the Phase 1 model as the baseline execution explanation and treat later phases as extensions of that pipeline rather than replacements.

## Recommended Validation

Before trusting dispatcher behavior after a change, run:

```bash
make lint
make contract-test
uv run pytest tests/Unit tests/Integration
make tickets-validate
```

For quick board hygiene alone:

```bash
make tickets-validate
```

## Normative Sources

- [../phase-1-dispatcher-mvp.md](../phase-1-dispatcher-mvp.md)
- [../routing-normalization.md](../routing-normalization.md)
- [../observability-contract.md](../observability-contract.md)
- [../safety-model.md](../safety-model.md)
- [../runtime-tooling.md](../runtime-tooling.md)