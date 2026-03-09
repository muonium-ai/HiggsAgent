"""Unit tests for local model executor stub."""

from __future__ import annotations

import pytest

from higgs_agent.providers.contract import (
    ExecutorInput,
    ExecutorLimits,
    ProviderToolDefinition,
)
from higgs_agent.providers.local.stub import (
    LocalModelExecutor,
    LocalModelExecutorError,
)
from higgs_agent.routing import RouteDecision

_LIMITS = ExecutorLimits(
    max_prompt_tokens=1000,
    max_completion_tokens=500,
    max_total_tokens=1500,
    max_cost_usd=1.0,
    max_tool_calls=10,
    provider_timeout_ms=5000,
    max_attempts=3,
)


def _route(
    selected: bool = True,
    provider: str = "local",
    blocked_reason: str | None = None,
) -> RouteDecision:
    return RouteDecision(
        ticket_id="T-001",
        priority="p1",
        selected=selected,
        provider=provider,
        model_id="local-model",
        route_family="local",
        estimated_cost_usd=0.0,
        requires_tool_calls=False,
        blocked_reason=blocked_reason,
        rationale=("test",),
    )


def _input(route: RouteDecision | None = None) -> ExecutorInput:
    return ExecutorInput(
        ticket_id="T-001",
        run_id="run-1",
        attempt_id="att-1",
        route=route or _route(),
        prompt="Hello",
    )


class FakeTransport:
    def __init__(self, response: dict[str, object] | Exception) -> None:
        self._response = response

    def generate(
        self, prompt: str, system_prompt: str | None, timeout_ms: int
    ) -> dict[str, object]:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_execute_succeeds_with_valid_transport() -> None:
    transport = FakeTransport({"output_text": "Hello back"})
    executor = LocalModelExecutor(limits=_LIMITS, transport=transport)
    result = executor.execute(_input())
    assert result.status == "succeeded"
    assert result.output_text == "Hello back"
    assert result.usage is not None
    assert len(result.events) > 0
    assert result.attempt_summary["final_result"] == "succeeded"


def test_execute_blocked_when_route_not_selected() -> None:
    route = _route(selected=False, blocked_reason="policy_block")
    transport = FakeTransport({"output_text": "should not reach"})
    executor = LocalModelExecutor(limits=_LIMITS, transport=transport)
    result = executor.execute(_input(route=route))
    assert result.status == "blocked"
    assert result.output_text == ""
    assert result.attempt_summary["final_result"] == "blocked"


def test_execute_blocked_when_provider_not_local() -> None:
    route = _route(provider="openrouter")
    transport = FakeTransport({"output_text": "should not reach"})
    executor = LocalModelExecutor(limits=_LIMITS, transport=transport)
    result = executor.execute(_input(route=route))
    assert result.status == "blocked"


def test_execute_rejects_tool_definitions() -> None:
    tool = ProviderToolDefinition(
        name="test", description="test tool", parameters={}
    )
    inp = ExecutorInput(
        ticket_id="T-001",
        run_id="run-1",
        attempt_id="att-1",
        route=_route(),
        prompt="Hello",
        tools=(tool,),
    )
    transport = FakeTransport({"output_text": "ok"})
    executor = LocalModelExecutor(limits=_LIMITS, transport=transport)
    with pytest.raises(LocalModelExecutorError, match="tool definitions"):
        executor.execute(inp)


def test_execute_handles_timeout() -> None:
    transport = FakeTransport(TimeoutError("timed out"))
    executor = LocalModelExecutor(limits=_LIMITS, transport=transport)
    result = executor.execute(_input())
    assert result.status == "failed"
    assert result.attempt_summary["final_result"] == "failed"


def test_execute_handles_transport_error() -> None:
    transport = FakeTransport(RuntimeError("connection refused"))
    executor = LocalModelExecutor(limits=_LIMITS, transport=transport)
    result = executor.execute(_input())
    assert result.status == "failed"


def test_execute_handles_invalid_payload() -> None:
    transport = FakeTransport("not a dict")  # type: ignore[arg-type]
    executor = LocalModelExecutor(limits=_LIMITS, transport=transport)
    result = executor.execute(_input())
    assert result.status == "failed"


def test_execute_parses_usage_from_response() -> None:
    transport = FakeTransport({
        "output_text": "ok",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    })
    executor = LocalModelExecutor(limits=_LIMITS, transport=transport)
    result = executor.execute(_input())
    assert result.status == "succeeded"
    assert result.usage is not None
    assert result.usage.tokens_prompt == 10
    assert result.usage.tokens_completion == 20
    assert result.usage.total_tokens == 30
