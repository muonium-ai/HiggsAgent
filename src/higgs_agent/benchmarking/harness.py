"""Comparable multi-provider benchmark harness execution."""

from __future__ import annotations

from dataclasses import dataclass, replace

from higgs_agent.providers.contract import (
    ExecutorInput,
    ProviderExecutionResult,
    ProviderExecutor,
    ProviderToolDefinition,
)
from higgs_agent.routing import RouteDecision

from .workloads import BenchmarkWorkload


class BenchmarkHarnessError(ValueError):
    """Raised when a benchmark harness request is invalid or unsafe."""


@dataclass(frozen=True, slots=True)
class BenchmarkCandidate:
    """One declared benchmark candidate and its executor boundary."""

    candidate_id: str
    route: RouteDecision
    executor: ProviderExecutor


@dataclass(frozen=True, slots=True)
class BenchmarkHarnessConfig:
    """Shared control-plane inputs applied to every benchmark candidate."""

    benchmark_id: str
    system_prompt: str = "You are HiggsAgent."
    executor_version: str = "phase-5-benchmark"
    repo_head: str | None = None
    tools: tuple[ProviderToolDefinition, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "benchmark_id": self.benchmark_id,
            "system_prompt": self.system_prompt,
            "executor_version": self.executor_version,
            "repo_head": self.repo_head,
            "tool_names": [tool.name for tool in self.tools],
        }


@dataclass(frozen=True, slots=True)
class BenchmarkCandidateResult:
    """Normalized execution result for one benchmark candidate."""

    candidate_id: str
    route: RouteDecision
    execution_input: ExecutorInput
    execution_result: ProviderExecutionResult


@dataclass(frozen=True, slots=True)
class BenchmarkHarnessResult:
    """Full comparable execution result set for one workload."""

    benchmark_id: str
    workload: BenchmarkWorkload
    shared_execution_context: dict[str, object]
    candidate_results: tuple[BenchmarkCandidateResult, ...]


def run_benchmark_workload(
    workload: BenchmarkWorkload,
    candidates: tuple[BenchmarkCandidate, ...],
    *,
    config: BenchmarkHarnessConfig,
    tool_invoker=None,
) -> BenchmarkHarnessResult:
    """Execute one workload across a declared candidate set."""

    _validate_workload(workload)
    _validate_candidates(workload, candidates)

    ticket_id = f"BENCH-{workload.workload_id}"
    prompt = _build_workload_prompt(workload)
    candidate_results: list[BenchmarkCandidateResult] = []
    for index, candidate in enumerate(candidates, start=1):
        route = replace(
            candidate.route,
            ticket_id=ticket_id,
            priority=workload.ticket_shape.priority,
            requires_tool_calls=workload.ticket_shape.tool_profile != "none",
        )
        execution_input = ExecutorInput(
            ticket_id=ticket_id,
            run_id=config.benchmark_id,
            attempt_id=f"{config.benchmark_id}-{index:02d}-{candidate.candidate_id}",
            route=route,
            prompt=prompt,
            system_prompt=config.system_prompt,
            executor_version=config.executor_version,
            repo_head=config.repo_head,
            allow_tool_calls=workload.ticket_shape.tool_profile != "none",
            tools=config.tools,
        )
        execution_result = candidate.executor.execute(execution_input, tool_invoker=tool_invoker)
        candidate_results.append(
            BenchmarkCandidateResult(
                candidate_id=candidate.candidate_id,
                route=route,
                execution_input=execution_input,
                execution_result=execution_result,
            )
        )

    return BenchmarkHarnessResult(
        benchmark_id=config.benchmark_id,
        workload=workload,
        shared_execution_context={
            **config.as_dict(),
            "workload_id": workload.workload_id,
            "candidate_ids": [candidate.candidate_id for candidate in candidates],
            "tool_profile": workload.ticket_shape.tool_profile,
            "execution_target": workload.ticket_shape.execution_target,
            "requires_repository_write": workload.requires_repository_write,
        },
        candidate_results=tuple(candidate_results),
    )


def _build_workload_prompt(workload: BenchmarkWorkload) -> str:
    return f"{workload.title}\n\n{workload.description}\n\n{workload.task}"


def _validate_workload(workload: BenchmarkWorkload) -> None:
    if workload.requires_repository_write:
        raise BenchmarkHarnessError("benchmark workloads requiring repository writes are unsupported")


def _validate_candidates(
    workload: BenchmarkWorkload,
    candidates: tuple[BenchmarkCandidate, ...],
) -> None:
    if not candidates:
        raise BenchmarkHarnessError("benchmark harness requires at least one candidate")

    candidate_ids = [candidate.candidate_id for candidate in candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise BenchmarkHarnessError("benchmark candidate ids must be unique")

    expected_tool_calls = workload.ticket_shape.tool_profile != "none"
    for candidate in candidates:
        if not candidate.candidate_id.strip():
            raise BenchmarkHarnessError("benchmark candidate ids must be non-empty")
        if not candidate.route.selected or candidate.route.blocked_reason is not None:
            raise BenchmarkHarnessError("benchmark candidates must be explicit eligible routes")
        if candidate.route.provider is None or candidate.route.model_id is None:
            raise BenchmarkHarnessError("benchmark candidates must declare provider and model")
        if candidate.route.requires_tool_calls != expected_tool_calls:
            raise BenchmarkHarnessError(
                "benchmark candidate tool-call requirement must match the workload tool profile"
            )