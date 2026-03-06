from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from higgs_agent.providers.contract import ExecutorInput, ProviderExecutionResult, ProviderUsage
from higgs_agent.providers.hosted import OpenRouterExecutor, load_executor_limits
from higgs_agent.providers.local import LocalModelExecutor
from higgs_agent.routing import choose_route, classify_ticket, load_route_guardrails


class FakeOpenRouterTransport:
    def complete(self, payload: dict[str, object], timeout_ms: int) -> dict[str, object]:
        del payload, timeout_ms
        return {
            "choices": [{"message": {"content": "Hosted output"}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "cost": 0.12,
            },
        }


class FakeLocalTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, str | None, int]] = []

    def generate(self, prompt: str, system_prompt: str | None, timeout_ms: int) -> dict[str, object]:
        self.calls.append((prompt, system_prompt, timeout_ms))
        return self.response


class RaisingLocalTransport:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def generate(self, prompt: str, system_prompt: str | None, timeout_ms: int) -> dict[str, object]:
        del prompt, system_prompt, timeout_ms
        raise self.error


def test_hosted_and_local_executors_share_provider_execution_result_shape() -> None:
    hosted_executor = OpenRouterExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=FakeOpenRouterTransport(),
    )
    local_executor = LocalModelExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=FakeLocalTransport(
            {
                "output_text": "Local output",
                "usage": {"prompt_tokens": 60, "completion_tokens": 15, "total_tokens": 75},
            }
        ),
    )

    hosted_result = hosted_executor.execute(_executor_input(execution_target="hosted"))
    local_result = local_executor.execute(_executor_input(execution_target="local"))

    assert isinstance(hosted_result, ProviderExecutionResult)
    assert isinstance(local_result, ProviderExecutionResult)
    assert hosted_result.output_text == "Hosted output"
    assert local_result.output_text == "Local output"

    _validate_attempt_summary(hosted_result.attempt_summary)
    _validate_attempt_summary(local_result.attempt_summary)
    _validate_event_stream(hosted_result.events)
    _validate_event_stream(local_result.events)


def test_local_executor_represents_partial_usage_without_fabricated_cost() -> None:
    transport = FakeLocalTransport(
        {
            "output_text": "Local partial usage",
            "usage": {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50},
        }
    )
    executor = LocalModelExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=transport,
    )

    result = executor.execute(_executor_input(execution_target="local"))

    assert result.status == "succeeded"
    assert transport.calls
    assert isinstance(result.usage, ProviderUsage)
    assert result.usage.total_tokens == 50
    assert result.usage.cost_usd is None
    assert result.usage.has_precise_billing is False
    assert result.attempt_summary["usage"]["total_tokens"] == 50
    assert "cost_usd" not in result.attempt_summary["usage"]


def test_local_executor_failure_preserves_schema_compatible_error_shapes() -> None:
    executor = LocalModelExecutor(
        limits=load_executor_limits(Path("config/guardrails.example.json")),
        transport=RaisingLocalTransport(TimeoutError("local runtime stalled")),
    )

    result = executor.execute(_executor_input(execution_target="local"))

    assert result.status == "failed"
    assert result.attempt_summary["final_result"] == "failed"
    assert result.attempt_summary["error"]["kind"] == "timeout"
    _validate_attempt_summary(result.attempt_summary)
    _validate_event_stream(result.events)


def _executor_input(*, execution_target: str) -> ExecutorInput:
    semantics = classify_ticket(
        {
            "id": f"T-{execution_target}",
            "type": "code",
            "priority": "p1",
            "effort": "m",
            "higgs_schema_version": 1,
            "higgs_platform": "repo",
            "higgs_execution_target": execution_target,
        }
    )
    route = choose_route(semantics, load_route_guardrails(Path("config/guardrails.example.json")))
    if execution_target == "local":
        route = route.__class__(
            ticket_id=route.ticket_id,
            priority=route.priority,
            selected=True,
            provider="local",
            model_id="llama3.1:8b",
            route_family="local",
            estimated_cost_usd=0.0,
            requires_tool_calls=False,
            blocked_reason=None,
            rationale=route.rationale + ("phase_3_local_executor",),
        )
    return ExecutorInput(
        ticket_id=f"T-{execution_target}",
        run_id="run-1",
        attempt_id="attempt-1",
        route=route,
        prompt="Implement the requested change.",
        system_prompt="You are HiggsAgent.",
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