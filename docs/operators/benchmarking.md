# Benchmarking Operations

## Audience

Operators and reviewers running or evaluating Phase 5 benchmark comparisons.

## Purpose

Explain what benchmark mode consumes, how to interpret benchmark outputs safely, and what to verify before treating benchmark results as meaningful provider or route comparisons.

## Current Phase 5 Boundary

Benchmarking is an explicit review mode, not the default dispatcher path.

- benchmark workloads come from curated manifests, not arbitrary live ticket selection
- benchmark execution runs the same workload across a declared candidate set using the existing provider execution boundary
- benchmark outputs reuse normalized execution artifacts and add review-oriented ranking and quality summaries
- benchmark runs do not authorize repository writes, hidden fanout in normal dispatch, or adaptive weight mutation

Operators should read benchmark output as a controlled comparison surface. It is evidence about a declared workload and candidate set, not a blanket production routing policy.

## What Benchmarking Consumes

Phase 5 benchmarking currently consumes three explicit inputs:

- reusable workload manifests loaded through `load_benchmark_workload_manifest()`
- declared benchmark candidates defined with provider, model, and eligible route metadata
- shared benchmark control-plane settings recorded through `BenchmarkHarnessConfig`

Operators should expect workloads to capture comparable ticket shape metadata such as:

- work type, priority, platform, and complexity
- execution target and tool profile
- success criteria and review tags

The benchmark corpus must not contain secret-bearing fields, raw prompts from prior runs, raw provider payloads, or repository-specific machine state.

## How To Run And Review Benchmarks

Review benchmark runs in this order:

1. confirm the workload is a curated manifest entry and does not require repository writes
2. confirm each candidate is an explicit eligible route with the expected provider, model, execution target, and tool-call profile
3. confirm the shared benchmark context records the benchmark ID, executor version, candidate ordering, and tool names
4. inspect normalized attempt summaries and execution events before trusting any derived ranking output
5. read the benchmark report table or serialized report only after the raw metrics look comparable

For a reproducible review, keep the workload, candidate set, and shared benchmark configuration fixed across reruns. If any of those change, treat the new run as a different comparison rather than an updated score.

## How To Interpret Rankings And Quality Signals

Benchmark reports intentionally separate measured outputs from derived interpretation.

Measured raw metrics include:

- final result status
- latency
- retry count
- tool-call count
- token usage when available
- precise hosted cost when available

Derived interpretation may include:

- explicit quality signals attached by the reviewer or fixture evaluation layer
- composite rank ordering based on the published ranking policy
- comparison notes for missing cost, missing latency, missing quality signals, or non-success outcomes

Operators should treat the ranking output conservatively:

1. ties mean the visible ranking inputs were equivalent; they are not hidden near-misses
2. missing metrics are a comparability warning, not proof of zero latency or zero cost
3. candidates without quality signals are still measurable, but their ranking should be read as incomplete
4. non-comparable candidate sets should be rejected before execution rather than rationalized after the fact

Do not turn a single benchmark win into a claim that one provider or route is universally superior.

## Safety, Retention, And Rollout Limits

Benchmarking keeps the earlier guardrails intact.

- benchmark workloads requiring repository writes are rejected
- benchmark mode remains separate from normal repository-writing dispatch flow
- normalized execution artifacts remain the review source of truth
- raw artifacts stay subject to local-only retention and secret-handling rules
- public reporting must distinguish measured outputs from inferred quality judgments

Benchmarking also does not mean adaptive scoring is now auto-tuned from benchmark outcomes. Any future use of benchmark results in routing policy needs separate contract and rollout work.

## Recommended Operator Checks

Before sharing or acting on benchmark results, verify:

- candidate ordering and benchmark configuration are captured in the shared execution context
- each candidate's attempt summary remains schema-compatible with existing observability and analytics expectations
- missing local cost data is treated as unavailable precision, not exact zero-cost accounting
- tied rankings and partial failures remain visible in the report output
- any exported artifacts remain safe under the retention and redaction rules

## Normative Sources

- [../phase-5-benchmarking-mode.md](../phase-5-benchmarking-mode.md)
- [../observability-contract.md](../observability-contract.md)
- [../phase-2-analytics-observability.md](../phase-2-analytics-observability.md)
- [../phase-2-analytics-metric-model.md](../phase-2-analytics-metric-model.md)
- [../storage-boundaries-and-retention.md](../storage-boundaries-and-retention.md)
- [../secret-handling.md](../secret-handling.md)