# Benchmarking Methodology

## Audience

Repository owners, evaluators, and external readers reviewing HiggsAgent benchmark claims.

## Purpose

Describe what HiggsAgent benchmark results mean, what they do not mean, and how to reproduce or review them without confusing benchmark mode with normal autonomous repository execution.

## What Phase 5 Benchmarking Measures

Phase 5 benchmarking compares declared candidates against the same curated workload.

A benchmark run consists of:

- one workload selected from the benchmark manifest corpus
- one explicit candidate set, where each candidate declares provider, model, and eligible route metadata
- one shared benchmark configuration capturing benchmark ID, executor version, repository head, and tool names
- one report derived from normalized execution artifacts and optional explicit quality signals

This gives HiggsAgent a reproducible way to compare measured outputs such as success state, latency, retries, tool usage, and precise hosted cost when available.

## What Benchmarking Does Not Measure

Phase 5 benchmarking is intentionally narrower than a public leaderboard.

It does not claim:

- universal provider quality outside the declared workload set
- repository-write safety for arbitrary live tickets
- zero-cost local execution when precise billing data is unavailable
- automatic improvement of adaptive routing or default dispatcher policy
- comparability across different workload shapes, tool profiles, or execution-target assumptions

If two runs differ in workload, candidate set, or shared configuration, they should be treated as different experiments.

## How To Read A Benchmark Report

Read benchmark output in layers:

1. start with the workload ID, candidate IDs, and shared benchmark context
2. inspect normalized raw metrics for each candidate
3. review any explicit quality signals and the rationale attached to them
4. inspect comparison notes for cost gaps, latency gaps, missing quality signals, ties, or non-success results
5. read the final rank ordering only after the inputs above look comparable

Important interpretation rules:

- ties mean the published ranking inputs matched; they are intentionally shown rather than broken invisibly
- missing metrics mean the comparison is weaker, not that the missing value is zero
- a report with partial failures can still be useful, but the failure state must remain visible
- ranking output is a summary, not a substitute for normalized execution artifacts

## Public Reproducibility Expectations

Anyone reviewing a benchmark claim should be able to identify:

- which workload manifest entry was used
- which provider and model candidates were included
- what benchmark configuration and tool profile were used
- whether the repository head or runtime version changed between runs
- whether quality signals came from a published rubric or fixture-specific reviewer logic

HiggsAgent Phase 5 supports reproducibility by recording benchmark configuration and reusing normalized execution artifacts as the source of truth for derived reports.

## Safety And Retention Expectations

Benchmarking remains subject to the same guardrails as the rest of HiggsAgent.

- benchmark workloads must be safe to retain and share under the repository retention rules
- benchmark runs do not authorize repository writes
- secret-bearing data, raw provider payloads, and ad hoc machine state are not valid benchmark inputs
- public reporting should prefer normalized outputs and reviewable derived summaries over raw provider artifacts

If a benchmark claim depends on hidden prompts, raw payloads, or unshareable repository state, it falls outside the published Phase 5 methodology.

## Review Checklist

Before trusting a published benchmark comparison, check:

- the workload and candidate set were explicitly declared
- the candidates were comparable on execution target and tool profile
- the report surfaced ties, missing metrics, and failures instead of hiding them
- the result was not presented as a default production routing recommendation
- the exported evidence stayed within the retention and redaction boundaries

## Normative Sources

- [../phase-5-benchmarking-mode.md](../phase-5-benchmarking-mode.md)
- [../architecture.md](../architecture.md)
- [../observability-contract.md](../observability-contract.md)
- [../storage-boundaries-and-retention.md](../storage-boundaries-and-retention.md)
- [../secret-handling.md](../secret-handling.md)