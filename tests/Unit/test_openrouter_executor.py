from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from higgs_agent.providers.contract import ExecutorInput, ProviderToolCall, ProviderToolDefinition
from higgs_agent.providers.hosted import OpenRouterExecutor, load_executor_limits
from higgs_agent.routing import choose_route, classify_ticket, load_route_guardrails


class FakeTransport:
    def __init__(self, responses: list[dict[str, object] | Exception]) -> None:
        self._responses = responses
        self.calls: list[tuple[dict[str, object], int]] = []

    def complete(self, payload: dict[str, object], timeout_ms: int) -> dict[str, object]:
        self.calls.append((payload, timeout_ms))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeToolInvoker:
    def __init__(self) -> None:
        self.invocations: list[ProviderToolCall] = []

    def invoke(self, tool_call: ProviderToolCall):
        self.invocations.append(tool_call)
        from higgs_agent.providers.contract import ProviderToolInvocationResult

        return ProviderToolInvocationResult(
            call_id=tool_call.call_id,
            name=tool_call.name,
            output_text=json.dumps({"ok": True}),
        )


def test_executor_produces_schema_valid_events_and_summary() -> None:
    executor = OpenRouterExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=FakeTransport([
            {
                "choices": [{"message": {"content": "Done"}}],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 30,
                    "total_tokens": 150,
                    "cost": 0.42,
                },
            }
        ]),
    )
    execution_input = _executor_input(ticket_type="docs")

    result = executor.execute(execution_input)

    assert result.status == "succeeded"
    assert result.output_text == "Done"
    _validate_event_stream(result.events)
    _validate_attempt_summary(result.attempt_summary)


def test_executor_invokes_tools_and_emits_tool_events() -> None:
    executor = OpenRouterExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=FakeTransport([
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {
                                        "name": "read_ticket",
                                        "arguments": "{\"ticket_id\": \"T-1\"}",
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
            }
        ]),
    )
    tool_invoker = FakeToolInvoker()
    execution_input = _executor_input(
        ticket_type="code",
        tool_profile="standard",
        tools=(
            ProviderToolDefinition(
                name="read_ticket",
                description="Read a ticket",
                parameters={"type": "object"},
            ),
        ),
    )

    result = executor.execute(execution_input, tool_invoker=tool_invoker)

    assert result.status == "succeeded"
    assert len(result.tool_calls) == 1
    assert [call.name for call in tool_invoker.invocations] == ["read_ticket"]
    assert [event["event_type"] for event in result.events].count("tool.call.started") == 1
    assert [event["event_type"] for event in result.events].count("tool.call.completed") == 1


def test_executor_retries_on_timeout_then_succeeds() -> None:
    executor = OpenRouterExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=FakeTransport(
            [
                TimeoutError("provider timed out"),
                {
                    "choices": [{"message": {"content": "Recovered"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            ]
        ),
    )

    result = executor.execute(_executor_input(ticket_type="tests"))

    assert result.status == "succeeded"
    assert result.retry_count == 1
    assert "retry.scheduled" in [event["event_type"] for event in result.events]


def test_executor_blocks_when_route_not_selected() -> None:
    semantics = classify_ticket(
        {
            "id": "T-blocked",
            "type": "code",
            "priority": "p0",
            "effort": "l",
            "higgs_schema_version": 1,
            "higgs_platform": "repo",
            "higgs_execution_target": "local",
        }
    )
    route = choose_route(semantics, load_route_guardrails(Path("config/guardrails.example.json")))
    executor = OpenRouterExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=FakeTransport([]),
    )

    result = executor.execute(
        ExecutorInput(
            ticket_id="T-blocked",
            run_id="run-1",
            attempt_id="attempt-1",
            route=route,
            prompt="Do work",
        )
    )

    assert result.status == "blocked"
    assert result.attempt_summary["final_result"] == "blocked"


def test_executor_fails_when_tool_calls_exceed_budget() -> None:
    executor = OpenRouterExecutor(
        limits=load_executor_limits(Path("tests/Fixtures/config/guardrails_tool_budget_one.json")),
        transport=FakeTransport([
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {"id": "call-1", "function": {"name": "a", "arguments": "{}"}},
                                {"id": "call-2", "function": {"name": "b", "arguments": "{}"}},
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
            }
        ]),
    )

    result = executor.execute(_executor_input(ticket_type="code"), tool_invoker=FakeToolInvoker())

    assert result.status == "failed"
    assert result.attempt_summary["error"]["kind"] == "guardrail"


def test_executor_requires_tool_invoker_when_tools_are_returned() -> None:
    executor = OpenRouterExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=FakeTransport([
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {"id": "call-1", "function": {"name": "a", "arguments": "{}"}}
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
            }
        ]),
    )

    result = executor.execute(
        _executor_input(
            ticket_type="code",
            tool_profile="standard",
            tools=(
                ProviderToolDefinition(
                    name="a",
                    description="Example tool",
                    parameters={"type": "object"},
                ),
            ),
        )
    )

    assert result.status == "failed"
    assert result.attempt_summary["error"]["kind"] == "tool"


def test_executor_limit_loader_rejects_missing_fields() -> None:
    with pytest.raises(ValueError, match="max_prompt_tokens"):
        load_executor_limits(Path("tests/Fixtures/config/guardrails_invalid_executor_limits.json"))


def _executor_input(
    *,
    ticket_type: str,
    tool_profile: str = "none",
    tools: tuple[ProviderToolDefinition, ...] = (),
) -> ExecutorInput:
    semantics = classify_ticket(
        {
            "id": "T-exec-1",
            "type": ticket_type,
            "priority": "p1",
            "effort": "m",
            "higgs_schema_version": 1,
            "higgs_platform": "agnostic",
            "higgs_tool_profile": tool_profile,
        }
    )
    route = choose_route(semantics, load_route_guardrails(Path("config/guardrails.example.json")))
    return ExecutorInput(
        ticket_id="T-exec-1",
        run_id="run-1",
        attempt_id="attempt-1",
        route=route,
        prompt="Implement the requested change.",
        system_prompt="You are HiggsAgent.",
        allow_tool_calls=tool_profile != "none",
        tools=tools,
    )


def _validate_event_stream(events: tuple[dict[str, object], ...]) -> None:
    event_schema = json.loads(Path("schemas/execution-event.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = Registry().with_resource(
        common_defs["$id"],
        Resource.from_contents(common_defs),
    ).with_resource(
        "common-defs.schema.json",
        Resource.from_contents(common_defs),
    )
    validator = jsonschema.Draft202012Validator(event_schema, registry=registry)
    for event in events:
        validator.validate(event)


def _validate_attempt_summary(summary: dict[str, object]) -> None:
    summary_schema = json.loads(Path("schemas/execution-attempt.schema.json").read_text())
    common_defs = json.loads(Path("schemas/common-defs.schema.json").read_text())
    registry = Registry().with_resource(
        common_defs["$id"],
        Resource.from_contents(common_defs),
    ).with_resource(
        "common-defs.schema.json",
        Resource.from_contents(common_defs),
    )
    validator = jsonschema.Draft202012Validator(summary_schema, registry=registry)
    validator.validate(summary)