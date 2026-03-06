"""OpenRouter-backed hosted executor boundary for Phase 1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Protocol

from higgs_agent.events import AttemptSummaryBuilder, EventStreamBuilder
from higgs_agent.providers.contract import (
    ExecutorInput,
    ExecutorLimits,
    ProviderToolCall,
    ProviderToolDefinition,
    ProviderToolInvocationResult,
    ProviderUsage,
)


class OpenRouterTransport(Protocol):
    """Transport abstraction for OpenRouter request execution."""

    def complete(self, payload: dict[str, object], timeout_ms: int) -> dict[str, object]:
        """Submit a completion request and return the raw response payload."""


class ToolInvoker(Protocol):
    """Boundary for executing provider-requested tools."""

    def invoke(self, tool_call: ProviderToolCall) -> ProviderToolInvocationResult:
        """Execute a tool call and return a normalized result."""


class OpenRouterExecutorError(ValueError):
    """Raised when executor configuration or response handling is invalid."""


@dataclass(frozen=True, slots=True)
class OpenRouterExecutionResult:
    """Normalized result returned by the hosted executor boundary."""

    status: str
    output_text: str
    tool_calls: tuple[ProviderToolCall, ...]
    usage: ProviderUsage | None
    events: tuple[dict[str, object], ...]
    attempt_summary: dict[str, object]
    retry_count: int


def load_executor_limits(config_path: Path) -> ExecutorLimits:
    """Load the executor-relevant guardrail limits from configuration."""

    payload = json.loads(config_path.read_text())
    limits = payload.get("limits")
    if not isinstance(limits, dict):
        raise OpenRouterExecutorError("guardrail config missing 'limits' object")

    required_fields = {
        "max_prompt_tokens": int,
        "max_completion_tokens": int,
        "max_total_tokens": int,
        "max_cost_usd": (int, float),
        "max_tool_calls": int,
        "provider_timeout_ms": int,
        "max_attempts": int,
    }
    for field_name, expected_type in required_fields.items():
        value = limits.get(field_name)
        if not isinstance(value, expected_type):
            raise OpenRouterExecutorError(f"guardrail config missing valid '{field_name}'")

    return ExecutorLimits(
        max_prompt_tokens=limits["max_prompt_tokens"],
        max_completion_tokens=limits["max_completion_tokens"],
        max_total_tokens=limits["max_total_tokens"],
        max_cost_usd=float(limits["max_cost_usd"]),
        max_tool_calls=limits["max_tool_calls"],
        provider_timeout_ms=limits["provider_timeout_ms"],
        max_attempts=limits["max_attempts"],
    )


@dataclass(slots=True)
class OpenRouterExecutor:
    """Guardrail-aware execution boundary for hosted OpenRouter requests."""

    limits: ExecutorLimits
    transport: OpenRouterTransport

    def execute(
        self,
        execution_input: ExecutorInput,
        *,
        tool_invoker: ToolInvoker | None = None,
    ) -> OpenRouterExecutionResult:
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

        if not execution_input.route.selected or execution_input.route.provider != "openrouter":
            events.append(
                "execution.completed",
                "blocked",
                payload={
                    "blocked_reason": execution_input.route.blocked_reason
                    or "route_not_selected"
                },
                limits=self.limits,
            )
            attempt_summary = summary.build(
                final_result="blocked",
                provider=execution_input.route.provider,
                model=execution_input.route.model_id,
                tool_call_count=0,
                retry_count=0,
                error={
                    "kind": "guardrail",
                    "message": execution_input.route.blocked_reason or "route_not_selected",
                    "retryable": False,
                },
            )
            return OpenRouterExecutionResult(
                status="blocked",
                output_text="",
                tool_calls=(),
                usage=None,
                events=events.build(),
                attempt_summary=attempt_summary,
                retry_count=0,
            )

        if not execution_input.allow_tool_calls and execution_input.tools:
            raise OpenRouterExecutorError("tool definitions provided while tool calls are disabled")

        events.append("guardrails.checked", "started", limits=self.limits)

        last_error: dict[str, object] | None = None
        retry_count = 0
        for attempt_index in range(self.limits.max_attempts):
            request_payload = self._build_request_payload(execution_input)
            events.append(
                "provider.requested",
                "started",
                payload={
                    "provider": execution_input.route.provider,
                    "model": execution_input.route.model_id,
                    "tool_count": len(execution_input.tools),
                    "attempt_index": attempt_index,
                },
                limits=self.limits,
            )

            started_at = monotonic()
            try:
                response_payload = self.transport.complete(
                    request_payload,
                    timeout_ms=self.limits.provider_timeout_ms,
                )
            except TimeoutError as exc:
                last_error = {"kind": "timeout", "message": str(exc), "retryable": True}
                events.append("provider.responded", "failed", error=last_error)
                if attempt_index < self.limits.max_attempts - 1:
                    retry_count += 1
                    events.append(
                        "retry.scheduled",
                        "retry_scheduled",
                        payload={"reason": "timeout", "attempt_index": attempt_index + 1},
                        error=last_error,
                    )
                    continue
                return self._failed_result(
                    events,
                    summary,
                    execution_input,
                    retry_count,
                    last_error,
                )
            except Exception as exc:
                last_error = {"kind": "provider", "message": str(exc), "retryable": True}
                events.append("provider.responded", "failed", error=last_error)
                if attempt_index < self.limits.max_attempts - 1:
                    retry_count += 1
                    events.append(
                        "retry.scheduled",
                        "retry_scheduled",
                        payload={"reason": "provider", "attempt_index": attempt_index + 1},
                        error=last_error,
                    )
                    continue
                return self._failed_result(
                    events,
                    summary,
                    execution_input,
                    retry_count,
                    last_error,
                )

            usage = _parse_usage(response_payload, int((monotonic() - started_at) * 1000))
            tool_calls = _parse_tool_calls(response_payload)
            output_text = _parse_output_text(response_payload)

            guardrail_error = self._guardrail_error(usage, tool_calls)
            if guardrail_error is not None:
                events.append(
                    "guardrails.checked",
                    "failed",
                    usage=usage,
                    limits=self.limits,
                    error=guardrail_error,
                )
                return self._failed_result(
                    events,
                    summary,
                    execution_input,
                    retry_count,
                    guardrail_error,
                    usage=usage,
                    tool_calls=tool_calls,
                )

            events.append(
                "guardrails.checked",
                "succeeded",
                usage=usage,
                limits=self.limits,
                payload={"tool_call_count": len(tool_calls)},
            )

            tool_error = self._handle_tool_calls(
                events,
                tool_calls,
                allow_tool_calls=execution_input.allow_tool_calls,
                tool_invoker=tool_invoker,
            )
            if tool_error is not None:
                return self._failed_result(
                    events,
                    summary,
                    execution_input,
                    retry_count,
                    tool_error,
                    usage=usage,
                    tool_calls=tool_calls,
                )

            events.append(
                "provider.responded",
                "succeeded",
                usage=usage,
                payload={
                    "provider": execution_input.route.provider,
                    "model": execution_input.route.model_id,
                    "tool_call_count": len(tool_calls),
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
                tool_call_count=len(tool_calls),
                retry_count=retry_count,
                usage=usage,
            )
            return OpenRouterExecutionResult(
                status="succeeded",
                output_text=output_text,
                tool_calls=tool_calls,
                usage=usage,
                events=events.build(),
                attempt_summary=attempt_summary,
                retry_count=retry_count,
            )

        fallback_error = last_error or {
            "kind": "internal",
            "message": "executor fell through",
            "retryable": False,
        }
        return self._failed_result(events, summary, execution_input, retry_count, fallback_error)

    def _build_request_payload(self, execution_input: ExecutorInput) -> dict[str, object]:
        if execution_input.route.model_id is None:
            raise OpenRouterExecutorError("route is missing model_id")

        messages: list[dict[str, object]] = []
        if execution_input.system_prompt:
            messages.append({"role": "system", "content": execution_input.system_prompt})
        messages.append({"role": "user", "content": execution_input.prompt})

        payload: dict[str, object] = {
            "model": execution_input.route.model_id,
            "messages": messages,
            "max_tokens": self.limits.max_completion_tokens,
        }
        if execution_input.allow_tool_calls and execution_input.tools:
            payload["tools"] = [_tool_definition_payload(tool) for tool in execution_input.tools]
        return payload

    def _guardrail_error(
        self,
        usage: ProviderUsage,
        tool_calls: tuple[ProviderToolCall, ...],
    ) -> dict[str, object] | None:
        if usage.total_tokens is not None and usage.total_tokens > self.limits.max_total_tokens:
            return {
                "kind": "guardrail",
                "message": "provider response exceeded max_total_tokens",
                "retryable": False,
            }
        if usage.cost_usd is not None and usage.cost_usd > self.limits.max_cost_usd:
            return {
                "kind": "guardrail",
                "message": "provider response exceeded max_cost_usd",
                "retryable": False,
            }
        if len(tool_calls) > self.limits.max_tool_calls:
            return {
                "kind": "guardrail",
                "message": "provider response exceeded max_tool_calls",
                "retryable": False,
            }
        return None

    def _handle_tool_calls(
        self,
        events: EventStreamBuilder,
        tool_calls: tuple[ProviderToolCall, ...],
        *,
        allow_tool_calls: bool,
        tool_invoker: ToolInvoker | None,
    ) -> dict[str, object] | None:
        if tool_calls and not allow_tool_calls:
            events.append(
                "execution.completed",
                "failed",
                error={
                    "kind": "guardrail",
                    "message": "tool calls were returned while tool usage is disabled",
                    "retryable": False,
                },
            )
            return {
                "kind": "guardrail",
                "message": "tool calls were returned while tool usage is disabled",
                "retryable": False,
            }

        if tool_calls and tool_invoker is None:
            events.append(
                "execution.completed",
                "failed",
                error={
                    "kind": "tool",
                    "message": "tool invoker required when provider emits tool calls",
                    "retryable": False,
                },
            )
            return {
                "kind": "tool",
                "message": "tool invoker required when provider emits tool calls",
                "retryable": False,
            }

        if tool_invoker is None:
            return None

        for tool_call in tool_calls:
            events.append(
                "tool.call.started",
                "started",
                payload={"tool_name": tool_call.name, "tool_call_id": tool_call.call_id},
            )
            invocation = tool_invoker.invoke(tool_call)
            events.append(
                "tool.call.completed",
                "succeeded" if invocation.success else "failed",
                payload={
                    "tool_name": invocation.name,
                    "tool_call_id": invocation.call_id,
                    "output_preview": invocation.output_text[:200],
                },
            )
        return None

    def _failed_result(
        self,
        events: EventStreamBuilder,
        summary: AttemptSummaryBuilder,
        execution_input: ExecutorInput,
        retry_count: int,
        error: dict[str, object],
        *,
        usage: ProviderUsage | None = None,
        tool_calls: tuple[ProviderToolCall, ...] = (),
    ) -> OpenRouterExecutionResult:
        events.append("execution.completed", "failed", usage=usage, error=error)
        attempt_summary = summary.build(
            final_result="failed",
            provider=execution_input.route.provider,
            model=execution_input.route.model_id,
            tool_call_count=len(tool_calls),
            retry_count=retry_count,
            usage=usage,
            error=error,
        )
        return OpenRouterExecutionResult(
            status="failed",
            output_text="",
            tool_calls=tool_calls,
            usage=usage,
            events=events.build(),
            attempt_summary=attempt_summary,
            retry_count=retry_count,
        )


def _tool_definition_payload(tool: ProviderToolDefinition) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _parse_output_text(response_payload: dict[str, object]) -> str:
    message = _response_message(response_payload)
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_value = item.get("text")
                if isinstance(text_value, str):
                    text_parts.append(text_value)
        return "\n".join(text_parts)
    return ""


def _parse_tool_calls(response_payload: dict[str, object]) -> tuple[ProviderToolCall, ...]:
    message = _response_message(response_payload)
    raw_tool_calls = message.get("tool_calls", [])
    if raw_tool_calls is None:
        return ()
    if not isinstance(raw_tool_calls, list):
        raise OpenRouterExecutorError("provider response tool_calls must be a list")

    parsed: list[ProviderToolCall] = []
    for index, tool_call in enumerate(raw_tool_calls):
        if not isinstance(tool_call, dict):
            raise OpenRouterExecutorError("provider tool call must be an object")
        function_payload = tool_call.get("function")
        if not isinstance(function_payload, dict):
            raise OpenRouterExecutorError("provider tool call missing function object")
        name = function_payload.get("name")
        arguments = function_payload.get("arguments", "{}")
        if not isinstance(name, str) or not name:
            raise OpenRouterExecutorError("provider tool call missing function name")
        if not isinstance(arguments, str):
            raise OpenRouterExecutorError("provider tool call arguments must be a JSON string")
        call_id = tool_call.get("id")
        parsed.append(
            ProviderToolCall(
                call_id=call_id if isinstance(call_id, str) and call_id else f"tool-call-{index}",
                name=name,
                arguments_json=arguments,
            )
        )
    return tuple(parsed)


def _parse_usage(response_payload: dict[str, object], latency_ms: int) -> ProviderUsage:
    raw_usage = response_payload.get("usage", {})
    if raw_usage is None:
        raw_usage = {}
    if not isinstance(raw_usage, dict):
        raise OpenRouterExecutorError("provider response usage must be an object")

    prompt_tokens = raw_usage.get("prompt_tokens")
    completion_tokens = raw_usage.get("completion_tokens")
    total_tokens = raw_usage.get("total_tokens")
    cost = raw_usage.get("cost")

    return ProviderUsage(
        tokens_prompt=prompt_tokens if isinstance(prompt_tokens, int) else None,
        tokens_completion=completion_tokens if isinstance(completion_tokens, int) else None,
        total_tokens=total_tokens if isinstance(total_tokens, int) else None,
        cost_usd=float(cost) if isinstance(cost, int | float) else None,
        latency_ms=latency_ms,
    )


def _response_message(response_payload: dict[str, object]) -> dict[str, object]:
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterExecutorError("provider response missing choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenRouterExecutorError("provider response choice must be an object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenRouterExecutorError("provider response choice missing message object")
    return message