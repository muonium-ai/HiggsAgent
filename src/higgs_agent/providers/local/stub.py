"""Local model executor boundary for Phase 3 hybrid execution."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from higgs_agent.events import AttemptSummaryBuilder, EventStreamBuilder
from higgs_agent.providers.contract import (
    ExecutorInput,
    ExecutorLimits,
    ProviderExecutionResult,
    ProviderUsage,
)


class LocalModelTransport(Protocol):
    """Transport abstraction for local model execution."""

    def generate(
        self, prompt: str, system_prompt: str | None, timeout_ms: int
    ) -> dict[str, object]:
        """Execute a local prompt and return a normalized raw payload."""


class LocalModelExecutorError(ValueError):
    """Raised when local executor configuration or responses are invalid."""


LocalExecutionResult = ProviderExecutionResult


@dataclass(slots=True)
class LocalModelExecutor:
    """Guardrail-aware local executor sharing the provider execution contract."""

    limits: ExecutorLimits
    transport: LocalModelTransport

    def execute(
        self, execution_input: ExecutorInput, *, tool_invoker=None
    ) -> ProviderExecutionResult:
        del tool_invoker

        events = EventStreamBuilder(
            run_id=execution_input.run_id,
            attempt_id=execution_input.attempt_id,
            ticket_id=execution_input.ticket_id,
            executor_version=execution_input.executor_version,
            repo_head=execution_input.repo_head,
        )
        summary = AttemptSummaryBuilder(
            run_id=execution_input.run_id,
            attempt_id=execution_input.attempt_id,
            ticket_id=execution_input.ticket_id,
        )

        events.append(
            "execution.created",
            "started",
            payload={
                "provider": execution_input.route.provider,
                "model": execution_input.route.model_id,
                "route_family": execution_input.route.route_family,
            },
            limits=self.limits,
        )

        if not execution_input.route.selected or execution_input.route.provider != "local":
            error = {
                "kind": "guardrail",
                "message": execution_input.route.blocked_reason or "route_not_selected",
                "retryable": False,
            }
            events.append(
                "execution.completed",
                "blocked",
                payload={
                    "blocked_reason": execution_input.route.blocked_reason or "route_not_selected"
                },
                error=error,
                limits=self.limits,
            )
            attempt_summary = summary.build(
                final_result="blocked",
                provider=execution_input.route.provider,
                model=execution_input.route.model_id,
                tool_call_count=0,
                retry_count=0,
                error=error,
            )
            return ProviderExecutionResult(
                status="blocked",
                output_text="",
                tool_calls=(),
                usage=None,
                events=events.build(),
                attempt_summary=attempt_summary,
                retry_count=0,
            )

        if execution_input.tools:
            raise LocalModelExecutorError(
                "local executor does not support tool definitions in Phase 3"
            )

        started_at = monotonic()
        try:
            response_payload = self.transport.generate(
                execution_input.prompt,
                execution_input.system_prompt,
                timeout_ms=self.limits.provider_timeout_ms,
            )
        except TimeoutError as exc:
            error = {"kind": "timeout", "message": str(exc), "retryable": True}
            return self._failed_result(events, summary, execution_input, error)
        except Exception as exc:
            error = {"kind": "provider", "message": str(exc), "retryable": True}
            return self._failed_result(events, summary, execution_input, error)

        try:
            if not isinstance(response_payload, dict):
                raise LocalModelExecutorError("local transport payload must be an object")

            latency_ms = int((monotonic() - started_at) * 1000)
            usage = _parse_local_usage(response_payload, latency_ms)
            output_text = response_payload.get("output_text", "")
            if not isinstance(output_text, str):
                raise LocalModelExecutorError("local transport output_text must be a string")
        except LocalModelExecutorError as exc:
            error = {"kind": "provider", "message": str(exc), "retryable": False}
            return self._failed_result(events, summary, execution_input, error)

        events.append(
            "provider.responded",
            "succeeded",
            usage=usage,
            payload={
                "provider": execution_input.route.provider,
                "model": execution_input.route.model_id,
                "usage_precision": "precise" if usage.has_precise_billing else "partial",
            },
        )
        events.append(
            "execution.completed",
            "completed",
            usage=usage,
            payload={"final_result": "succeeded"},
        )
        attempt_summary = summary.build(
            final_result="succeeded",
            provider=execution_input.route.provider,
            model=execution_input.route.model_id,
            tool_call_count=0,
            retry_count=0,
            usage=usage,
        )
        return ProviderExecutionResult(
            status="succeeded",
            output_text=output_text,
            tool_calls=(),
            usage=usage,
            events=events.build(),
            attempt_summary=attempt_summary,
            retry_count=0,
        )

    def _failed_result(
        self,
        events: EventStreamBuilder,
        summary: AttemptSummaryBuilder,
        execution_input: ExecutorInput,
        error: dict[str, object],
    ) -> ProviderExecutionResult:
        events.append("provider.responded", "failed", error=error)
        events.append("execution.completed", "failed", error=error)
        attempt_summary = summary.build(
            final_result="failed",
            provider=execution_input.route.provider,
            model=execution_input.route.model_id,
            tool_call_count=0,
            retry_count=0,
            error=error,
        )
        return ProviderExecutionResult(
            status="failed",
            output_text="",
            tool_calls=(),
            usage=None,
            events=events.build(),
            attempt_summary=attempt_summary,
            retry_count=0,
        )


def _parse_local_usage(response_payload: dict[str, object], latency_ms: int) -> ProviderUsage:
    usage_payload = response_payload.get("usage", {})
    if usage_payload is None:
        usage_payload = {}
    if not isinstance(usage_payload, dict):
        raise LocalModelExecutorError("local transport usage must be an object")

    prompt_tokens = usage_payload.get("prompt_tokens")
    completion_tokens = usage_payload.get("completion_tokens")
    total_tokens = usage_payload.get("total_tokens")
    cost = usage_payload.get("cost")

    return ProviderUsage(
        tokens_prompt=prompt_tokens if isinstance(prompt_tokens, int) else None,
        tokens_completion=completion_tokens if isinstance(completion_tokens, int) else None,
        total_tokens=total_tokens if isinstance(total_tokens, int) else None,
        cost_usd=float(cost) if isinstance(cost, int | float) else None,
        latency_ms=latency_ms,
    )
