# Adaptive Dispatch Operations

## Audience

Operators and reviewers evaluating adaptive route scoring outputs and rollout safety.

## Purpose

Explain what Phase 4 adaptive dispatch currently consumes, what it can and cannot change, how to interpret its scoring output, and what to verify before trusting adaptive behavior in reviews or future rollout steps.

## Current Phase 4 Boundary

Phase 4 adds an adaptive scoring surface, not a replacement control plane.

- adaptive scoring consumes normalized telemetry and ranks already-eligible route candidates
- execution-target rules, provider eligibility, guardrails, validation, and the write gate remain hard boundaries
- adaptive scoring now exposes a serializable metadata payload with ranked candidates, exclusions, weights, tie-break policy, and route-level explanations
- the live dispatcher path is not yet switched over to adaptive route choice by default

Operators should read current adaptive output as an explainable review surface and a validated contract for later rollout work, not as permission to bypass deterministic routing rules.

## Telemetry Inputs And Out Of Scope Inputs

Adaptive scoring is allowed to consume only normalized telemetry.

Primary inputs today are:

- normalized execution attempt summaries
- normalized analytics aggregate records

Operators should expect those telemetry surfaces to carry:

- success, failure, blocked, retry, and tool-call history
- average duration and token signals where available
- exact hosted cost when available
- freshness state and explicit telemetry gaps

The following remain out of scope for scoring and should not appear as hidden ranking inputs:

- raw prompts or prompt fragments
- raw provider payloads or full responses
- secret-bearing artifacts, headers, or environment values
- opaque provider-specific heuristics outside the inspectable scoring model
- external telemetry services as a required policy control plane

## How To Interpret Scores

Adaptive scores are weighted summaries over already-eligible candidates.

The current inspectable factors are:

- success history
- failure history
- retry pressure
- latency signal
- cost signal
- capability fit against ticket shape

Operators should review the adaptive payload in this order:

1. confirm that excluded candidates were blocked for explicit reasons such as execution-target incompatibility or non-eligible route state
2. confirm that the selected route still matches the allowed candidate set after deterministic routing and guardrails
3. inspect `scoring_weights`, `tie_break_policy`, and each candidate explanation rather than inferring hidden heuristics
4. treat `used_deterministic_defaults=true` or `telemetry_gaps` entries as a signal that stale or missing telemetry reduced confidence

The tie-break policy is deterministic. If two candidates land on the same total score, lower estimated cost wins first, then provider and model lexical ordering.

## Guardrails And Explicit Operator Intent

Adaptive scoring cannot override the existing safety boundaries.

- `higgs_execution_target=hosted` still excludes local candidates
- `higgs_execution_target=local` still excludes hosted candidates
- blocked or non-selected deterministic candidates remain excluded even if their historical telemetry looks strong
- fallback remains bounded and observable; adaptive scoring does not authorize unbounded retries
- write-gate and protected-path handling remain unchanged

If adaptive output and deterministic route eligibility appear to conflict, treat that as a review issue, not as grounds to trust the adaptive score over the guardrails.

## Observability And Analytics Expectations

When adaptive scoring is enabled in a workflow, operators should expect observability differences in metadata rather than schema replacement.

- execution events can carry adaptive selection metadata inside their payloads
- the adaptive payload should include selected-route metadata, ranked candidates, excluded candidates, scoring weights, tie-break policy, and telemetry source
- telemetry gaps should remain explicit instead of being hidden by provider-specific defaults
- attempt-summary schemas remain unchanged and continue to carry normalized provider, model, retry, and usage fields
- analytics aggregation still consumes normalized attempt summaries rather than the adaptive metadata payload itself

This means analytics totals remain comparable across deterministic, hybrid, and adaptive-aware review paths. Adaptive metadata adds explanation, not a new accounting schema.

## Remaining Limits And Safe Rollout Expectations

Phase 4 is still intentionally narrow.

- no online learning or self-modifying weights
- no external hosted scoring service
- no benchmark-style multi-provider live fanout
- no hidden provider adapter logic that bypasses the published weighting model
- no claim that adaptive scoring is already the default dispatcher route chooser

For safe rollout, operators should:

- compare adaptive explanations against the existing deterministic route rationale before trusting new behavior
- treat stale telemetry as lower-confidence input even though the scorer degrades to deterministic defaults
- verify local cost gaps are interpreted as unavailable precision, not true zero-cost proof
- require tighter review for any change that claims adaptive scoring now influences the live dispatcher path

## Normative Sources

- [../phase-4-adaptive-dispatch.md](../phase-4-adaptive-dispatch.md)
- [../observability-contract.md](../observability-contract.md)
- [../phase-2-analytics-observability.md](../phase-2-analytics-observability.md)
- [../phase-2-analytics-metric-model.md](../phase-2-analytics-metric-model.md)
- [../runtime-tooling.md](../runtime-tooling.md)