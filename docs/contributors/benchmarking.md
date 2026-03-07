# Benchmarking Development

## Audience

Contributors changing benchmark workloads, harness execution, reporting, or later benchmark integrations.

## Purpose

Explain the current Phase 5 implementation boundary so contributor changes preserve comparability, reproducibility, observability compatibility, and the separation between benchmark review mode and the default dispatch path.

## Source Contracts

Benchmarking work must stay aligned with:

- [../phase-5-benchmarking-mode.md](../phase-5-benchmarking-mode.md)
- [../phase-1-dispatcher-mvp.md](../phase-1-dispatcher-mvp.md)
- [../phase-2-analytics-observability.md](../phase-2-analytics-observability.md)
- [../phase-2-analytics-metric-model.md](../phase-2-analytics-metric-model.md)
- [../phase-3-hybrid-execution.md](../phase-3-hybrid-execution.md)
- [../phase-4-adaptive-dispatch.md](../phase-4-adaptive-dispatch.md)
- [../observability-contract.md](../observability-contract.md)
- [../runtime-tooling.md](../runtime-tooling.md)

## Current Implementation Boundary

Phase 5 currently delivers three benchmark surfaces:

- curated workload manifests in `higgs_agent.benchmarking.workloads`
- isolated comparative execution in `higgs_agent.benchmarking.harness`
- ranking and quality reporting in `higgs_agent.benchmarking.reporting`

Keep these distinctions clear:

- benchmarking is explicit fanout over a declared candidate set, not hidden dispatcher behavior
- workloads are curated fixtures with comparable ticket-shape metadata, not harvested live tickets
- benchmark runs must preserve normalized `ExecutorInput` and `ProviderExecutionResult` compatibility
- ranking builds on normalized outputs and explicit quality signals rather than provider-specific hidden heuristics
- repository-writing workloads remain out of scope for benchmark execution

## Workload Rules

Manifest changes must keep the corpus safe and comparable.

- use `BenchmarkWorkloadManifest`, `BenchmarkWorkload`, and `BenchmarkTicketShape` as the contract surface
- keep `schema_version` stable unless there is an intentional migration plan
- reject secret-bearing keys, raw provider payloads, and unsupported manifest fields
- preserve the comparable ticket-shape fields: work type, priority, platform, complexity, execution target, and tool profile
- treat `requires_repository_write=true` as invalid for current benchmark execution

If a proposed workload cannot be safely shared or cannot support apples-to-apples candidate comparison, it does not belong in the Phase 5 corpus.

## Harness Rules

Changes to benchmark execution must preserve explicit, reproducible control-plane behavior.

- use `BenchmarkHarnessConfig` to capture benchmark ID, executor version, repo head, and tool names
- use `BenchmarkCandidate` to declare the candidate ID, eligible route, and executor boundary
- keep candidate ordering deterministic for the same input set
- reject blocked, underspecified, duplicate, or tool-profile-incompatible candidates before execution
- continue to reuse normalized executor contracts instead of creating benchmark-only raw result schemas

The benchmark harness is allowed to reuse hybrid and adaptive-compatible route metadata, but it must not bypass provider eligibility, execution-target constraints, or write-gate assumptions.

## Reporting And Methodology Rules

Changes to benchmark reporting must keep interpretation inspectable.

- raw metrics stay visible even when rankings are rendered
- `BenchmarkQualitySignal` remains explicit and reviewable
- tie detection must be based on visible ranking inputs, not a hidden ordering field
- missing cost, latency, or quality signals must stay visible through comparison notes
- report output must not imply unsupported claims such as universal provider quality or production routing policy

Treat `BenchmarkReport.to_dict()` and `render_benchmark_report_table()` as compatibility surfaces. If their semantics change, update tests and operator or adopter docs in the same change.

## Safe Change Rules

When changing benchmark behavior:

- update tests and docs in the same change
- preserve observability and analytics compatibility with normalized artifacts
- keep benchmark mode distinct from the default repository-writing path
- keep benchmark configuration capture explicit enough for rerun review
- reject non-comparable inputs early instead of inventing post-hoc normalization

Require tighter review if a change:

- broadens benchmark workloads toward repository writes
- changes candidate ranking policy or tie semantics
- changes what counts as comparable tool or execution-target requirements
- adds hidden quality heuristics inside provider adapters or executors
- claims benchmark outputs should directly modify adaptive routing behavior

## Recommended Validation

For benchmark-focused changes, run:

```bash
uv run pytest tests/Unit/test_benchmark_workloads.py \
  tests/Unit/test_benchmark_harness.py \
  tests/Unit/test_benchmark_reporting.py \
  tests/Integration/test_benchmark_pipeline.py

uv run pytest tests/Unit/test_analytics_reporting.py \
  tests/Integration/test_analytics_reporting_pipeline.py

make tickets-validate
```

Run broader validation when changes touch shared routing contracts, provider result schemas, or public observability payloads.

## Phase 5 Limits

Do not quietly expand Phase 5 beyond its current contract.

- no hidden benchmark fanout in standard dispatch
- no automatic benchmark ingestion from arbitrary repository tickets
- no repository writes during comparative benchmark runs
- no required external leaderboard or hosted policy control plane
- no unsupported claim that benchmark wins are sufficient to choose production routing defaults

Phase 5 now provides reusable benchmark fixtures, a comparable execution harness, ranking and quality outputs, and contract coverage. Later work is still required before benchmark results can justify live policy changes.