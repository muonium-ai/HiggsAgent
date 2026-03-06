# Hybrid Execution Operations

## Audience

Operators and reviewers running or evaluating hosted versus local HiggsAgent execution.

## Purpose

Explain the current Phase 3 hybrid runtime prerequisites, deterministic selection rules, fallback behavior, observability differences, and unsupported scenarios.

## Runtime Prerequisites

Hybrid execution keeps the repository runtime model unchanged:

- HiggsAgent itself remains Python 3.12+ and `uv` managed.
- Hosted execution continues to use the existing provider boundary.
- Local execution is optional and depends on an operator-provided local model runtime outside the repository.

Before expecting local routes to run, confirm all of the following:

- the local runtime or daemon is installed separately and reachable from the HiggsAgent process
- the runtime is wired into the local provider transport boundary used by the application
- the active workflow does not require tool definitions for explicit local execution
- the operator understands that exact local billing data may be unavailable

If those prerequisites are not met, local-targeted tickets should be treated as blocked by configuration rather than silently redirected.

## Selection Rules

Phase 3 hybrid selection is deterministic.

- `higgs_execution_target=hosted`: always uses hosted routing.
- `higgs_execution_target=local`: selects the local route only when a local runtime is configured and the request is toolless.
- `higgs_execution_target=auto`: may prefer local execution only for low-risk, toolless work where the routing policy explicitly allows it.

Current auto-local preference is intentionally narrow. Operators should expect hosted selection for:

- higher-capability code and refactor work
- platform-sensitive tickets
- any request requiring tool support
- any workflow where no local runtime is configured

## Fallback Behavior

Fallback is also deterministic and bounded.

- Failed auto-local attempts may fall back to hosted execution.
- Explicit local requests do not fall back to hosted execution, because that would violate operator intent.
- Fallback does not bypass guardrails, validation, or the write gate.

When fallback occurs, the execution record should show:

- the original local route rationale
- fallback metadata identifying the hosted route
- a `retry.scheduled` event for the bounded fallback step
- a second route-selection event describing the hosted fallback route

## Observability And Analytics Differences

Hosted and local attempts share the same event and attempt-summary schemas, but operators should expect a few differences.

- Hosted attempts may include precise `cost_usd` metrics.
- Local attempts may emit partial usage only, such as token totals and latency without exact cost.
- Fallback records include additional metadata describing the primary and fallback routes.
- Analytics reports can group local and hosted attempts by provider and model without inspecting provider-specific payloads.

Treat local aggregate cost totals carefully: missing local billing data is represented as unavailable at the attempt layer and should not be interpreted as precise zero-cost accounting.

## Remaining Phase 3 Limits

The following scenarios remain unsupported or intentionally deferred in this phase:

- automatic discovery or installation of a local runtime
- hosted-to-local fallback
- adaptive scoring between hosted and local routes
- tool-enabled explicit local execution
- production packaging guidance for local inference stacks
- platform-specific operator guidance beyond macOS and Linux

## Recommended Operator Checks

Before trusting a hybrid run, verify:

- the route rationale matches the ticket execution target and shape
- fallback metadata is present only when fallback actually occurred
- local attempts without `cost_usd` are treated as partial metrics, not accounting truth
- export decisions still respect `source.export_safe` and local-only retention boundaries

## Normative Sources

- [../phase-3-hybrid-execution.md](../phase-3-hybrid-execution.md)
- [../runtime-tooling.md](../runtime-tooling.md)
- [../observability-contract.md](../observability-contract.md)
- [../storage-boundaries-and-retention.md](../storage-boundaries-and-retention.md)
- [../secret-handling.md](../secret-handling.md)