"""Shared provider-facing execution models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from higgs_agent.routing import RouteDecision


@dataclass(frozen=True, slots=True)
class ProviderToolDefinition:
    """Callable tool exposed to the provider boundary."""

    name: str
    description: str
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class ProviderToolCall:
    """Normalized provider-emitted tool call."""

    call_id: str
    name: str
    arguments_json: str


@dataclass(frozen=True, slots=True)
class ProviderToolInvocationResult:
    """Result returned by the tool-call boundary."""

    call_id: str
    name: str
    output_text: str
    success: bool = True


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    """Normalized provider usage metrics aligned to the observability schema."""

    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None

    @property
    def has_precise_billing(self) -> bool:
        """Whether the usage payload includes exact billing data."""

        return self.cost_usd is not None

    def as_schema_payload(self) -> dict[str, int | float]:
        payload: dict[str, int | float] = {}
        if self.tokens_prompt is not None:
            payload["tokens_prompt"] = self.tokens_prompt
        if self.tokens_completion is not None:
            payload["tokens_completion"] = self.tokens_completion
        if self.total_tokens is not None:
            payload["total_tokens"] = self.total_tokens
        if self.cost_usd is not None:
            payload["cost_usd"] = self.cost_usd
        if self.latency_ms is not None:
            payload["latency_ms"] = self.latency_ms
        return payload


@dataclass(frozen=True, slots=True)
class ExecutorArtifactRef:
    """Artifact reference emitted by executor events and summaries."""

    path: str
    scope: str
    sha256: str | None = None
    size_bytes: int | None = None

    def as_schema_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"path": self.path, "scope": self.scope}
        if self.sha256 is not None:
            payload["sha256"] = self.sha256
        if self.size_bytes is not None:
            payload["size_bytes"] = self.size_bytes
        return payload


@dataclass(frozen=True, slots=True)
class ExecutorLimits:
    """Guardrail limits required by the executor boundary."""

    max_prompt_tokens: int
    max_completion_tokens: int
    max_total_tokens: int
    max_cost_usd: float
    max_tool_calls: int
    provider_timeout_ms: int
    max_attempts: int

    def as_event_limits(self) -> dict[str, int | float]:
        return {
            "max_prompt_tokens": self.max_prompt_tokens,
            "max_completion_tokens": self.max_completion_tokens,
            "max_total_tokens": self.max_total_tokens,
            "max_cost_usd": self.max_cost_usd,
            "max_tool_calls": self.max_tool_calls,
            "timeout_ms": self.provider_timeout_ms,
        }


@dataclass(frozen=True, slots=True)
class ExecutorInput:
    """Execution request passed into the hosted provider boundary."""

    ticket_id: str
    run_id: str
    attempt_id: str
    route: RouteDecision
    prompt: str
    system_prompt: str | None = None
    executor_version: str = "phase-1"
    repo_head: str | None = None
    allow_tool_calls: bool = True
    tools: tuple[ProviderToolDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderExecutionResult:
    """Normalized execution result shared by hosted and local provider adapters."""

    status: str
    output_text: str
    tool_calls: tuple[ProviderToolCall, ...]
    usage: ProviderUsage | None
    events: tuple[dict[str, object], ...]
    attempt_summary: dict[str, object]
    retry_count: int
    metadata: dict[str, object] = field(default_factory=dict)


class ProviderExecutor(Protocol):
    """Shared executor boundary used by hosted and local provider adapters."""

    def execute(
        self, execution_input: ExecutorInput, *, tool_invoker=None
    ) -> ProviderExecutionResult:
        """Execute a route and return a normalized provider result."""
