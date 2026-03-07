"""Deterministic dispatcher orchestration for hybrid execution integration tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from higgs_agent.events.records import utc_now_iso
from higgs_agent.providers.contract import ExecutorInput, ProviderExecutionResult
from higgs_agent.providers.hosted import OpenRouterTransport
from higgs_agent.routing import NormalizedTicketSemantics, RouteDecision
from higgs_agent.tickets import TicketRecord, scan_ticket_directory, select_next_ready_ticket
from higgs_agent.validation import ProposedFileChange, ValidationDecision


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    """End-to-end deterministic dispatch result for a single ticket."""

    ticket: TicketRecord
    semantics: NormalizedTicketSemantics
    route: RouteDecision
    execution_result: ProviderExecutionResult
    validation_decision: ValidationDecision


def dispatch_next_ready_ticket(
    tickets_dir: Path,
    *,
    transport: OpenRouterTransport,
    local_transport=None,
    guardrails_path: Path,
    write_policy_path: Path,
    planned_changes: tuple[ProposedFileChange, ...],
    validation_summary: str,
    tool_invoker=None,
    diff_is_deterministic: bool = True,
    run_id: str = "run-1",
    attempt_id: str = "attempt-1",
    repo_head: str | None = None,
    requirements_text: str | None = None,
) -> DispatchOutcome | None:
    """Run the deterministic hybrid dispatcher pipeline for the next ready ticket."""

    from higgs_agent.providers.hosted import OpenRouterExecutor, load_executor_limits
    from higgs_agent.providers.local import LocalModelExecutor
    from higgs_agent.routing import choose_route, classify_ticket, load_route_guardrails
    from higgs_agent.validation import ValidationInput, evaluate_write_request, load_write_policy

    scan_result = scan_ticket_directory(tickets_dir)
    ticket = select_next_ready_ticket(scan_result)
    if ticket is None:
        return None

    semantics = classify_ticket(ticket)
    route_guardrails = load_route_guardrails(guardrails_path)
    route = choose_route(
        semantics,
        route_guardrails,
        local_execution_enabled=local_transport is not None,
    )
    execution_input = ExecutorInput(
        ticket_id=ticket.id,
        run_id=run_id,
        attempt_id=attempt_id,
        route=route,
        prompt=_build_prompt(ticket, requirements_text=requirements_text),
        system_prompt="You are HiggsAgent.",
        repo_head=repo_head,
        allow_tool_calls=route.requires_tool_calls,
    )
    executor = _executor_for_route(
        route,
        guardrails_path=guardrails_path,
        hosted_transport=transport,
        local_transport=local_transport,
    )
    execution_result = executor.execute(execution_input, tool_invoker=tool_invoker)
    execution_result = replace(
        execution_result,
        metadata={
            **execution_result.metadata,
            "primary_route": _route_metadata(route),
            "route_rationale": list(route.rationale),
            "fallback_triggered": False,
        },
    )

    if _should_fallback_to_hosted(semantics, route, execution_result):
        fallback_route = choose_route(semantics, route_guardrails, local_execution_enabled=False)
        execution_result = _execute_hosted_fallback(
            execution_input=execution_input,
            primary_route=route,
            primary_result=execution_result,
            fallback_route=fallback_route,
            guardrails_path=guardrails_path,
            hosted_transport=transport,
            tool_invoker=tool_invoker,
        )

    validation_decision = evaluate_write_request(
        ValidationInput(
            ticket_id=ticket.id,
            run_id=run_id,
            attempt_id=attempt_id,
            executor_status=execution_result.status,
            output_text=execution_result.output_text,
            changed_files=planned_changes,
            validation_summary=validation_summary,
            usage=execution_result.usage,
            diff_is_deterministic=diff_is_deterministic,
        ),
        load_write_policy(write_policy_path),
    )
    execution_result = _with_validation_events(execution_result, validation_decision)

    return DispatchOutcome(
        ticket=ticket,
        semantics=semantics,
        route=route,
        execution_result=execution_result,
        validation_decision=validation_decision,
    )


def _build_prompt(ticket: TicketRecord, *, requirements_text: str | None = None) -> str:
    title = ticket.frontmatter.get("title", ticket.id)
    body = ticket.body.strip()
    sections: list[str] = []
    if requirements_text and requirements_text.strip():
        sections.append(f"Project requirements:\n\n{requirements_text.strip()}")
    sections.append(str(title))
    if not body:
        return "\n\n".join(sections)
    sections.append(body)
    return "\n\n".join(sections)


def _executor_for_route(
    route: RouteDecision,
    *,
    guardrails_path: Path,
    hosted_transport: OpenRouterTransport,
    local_transport,
):
    from higgs_agent.providers.hosted import OpenRouterExecutor, load_executor_limits
    from higgs_agent.providers.local import LocalModelExecutor

    limits = load_executor_limits(guardrails_path)
    if route.provider == "local" and local_transport is not None:
        return LocalModelExecutor(limits=limits, transport=local_transport)
    return OpenRouterExecutor(limits=limits, transport=hosted_transport)


def _should_fallback_to_hosted(
    semantics: NormalizedTicketSemantics,
    route: RouteDecision,
    result: ProviderExecutionResult,
) -> bool:
    return (
        semantics.execution_target == "auto"
        and route.provider == "local"
        and result.status == "failed"
    )


def _execute_hosted_fallback(
    *,
    execution_input: ExecutorInput,
    primary_route: RouteDecision,
    primary_result: ProviderExecutionResult,
    fallback_route: RouteDecision,
    guardrails_path: Path,
    hosted_transport: OpenRouterTransport,
    tool_invoker,
) -> ProviderExecutionResult:
    fallback_metadata = {
        "primary_route": _route_metadata(primary_route),
        "fallback_route": _route_metadata(fallback_route),
        "route_rationale": list(primary_route.rationale),
        "fallback_triggered": True,
        "fallback_reason": primary_result.attempt_summary.get("error", {}).get("kind", "provider"),
    }
    if not fallback_route.selected:
        return replace(primary_result, metadata={**primary_result.metadata, **fallback_metadata})

    fallback_input = replace(
        execution_input,
        attempt_id=f"{execution_input.attempt_id}-fallback-1",
        route=fallback_route,
        allow_tool_calls=fallback_route.requires_tool_calls,
    )
    fallback_executor = _executor_for_route(
        fallback_route,
        guardrails_path=guardrails_path,
        hosted_transport=hosted_transport,
        local_transport=None,
    )
    fallback_result = fallback_executor.execute(fallback_input, tool_invoker=tool_invoker)
    fallback_attempt_summary = dict(fallback_result.attempt_summary)
    fallback_attempt_summary["retry_count"] = primary_result.retry_count + fallback_result.retry_count + 1

    combined_events = _resequenced_events(
        primary_result.events
        + (
            _dispatcher_event(
                event_type="retry.scheduled",
                status="retry_scheduled",
                run_id=execution_input.run_id,
                attempt_id=execution_input.attempt_id,
                ticket_id=execution_input.ticket_id,
                executor_version=execution_input.executor_version,
                repo_head=execution_input.repo_head,
                sequence=len(primary_result.events),
                payload={
                    "reason": "local_provider_failed",
                    "from_provider": primary_route.provider,
                    "to_provider": fallback_route.provider,
                    "from_model": primary_route.model_id,
                    "to_model": fallback_route.model_id,
                },
                error=primary_result.attempt_summary.get("error"),
            ),
            _dispatcher_event(
                event_type="route.selected",
                status="succeeded",
                run_id=execution_input.run_id,
                attempt_id=execution_input.attempt_id,
                ticket_id=execution_input.ticket_id,
                executor_version=execution_input.executor_version,
                repo_head=execution_input.repo_head,
                sequence=len(primary_result.events) + 1,
                payload={
                    "provider": fallback_route.provider,
                    "model": fallback_route.model_id,
                    "route_family": fallback_route.route_family,
                    "rationale": list(fallback_route.rationale),
                    "selection_reason": "bounded_fallback",
                },
            ),
        )
        + fallback_result.events
    )

    return replace(
        fallback_result,
        events=combined_events,
        attempt_summary=fallback_attempt_summary,
        retry_count=primary_result.retry_count + fallback_result.retry_count + 1,
        metadata={**fallback_result.metadata, **fallback_metadata},
    )


def _resequenced_events(events: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
    normalized_events: list[dict[str, object]] = []
    for index, event in enumerate(events):
        normalized_event = dict(event)
        normalized_event["sequence"] = index
        normalized_events.append(normalized_event)
    return tuple(normalized_events)


def _route_metadata(route: RouteDecision) -> dict[str, object]:
    return {
        "selected": route.selected,
        "provider": route.provider,
        "model_id": route.model_id,
        "route_family": route.route_family,
        "blocked_reason": route.blocked_reason,
    }


def _dispatcher_event(
    *,
    event_type: str,
    status: str,
    run_id: str,
    attempt_id: str,
    ticket_id: str,
    executor_version: str,
    repo_head: str | None,
    sequence: int,
    payload: dict[str, object] | None = None,
    error: dict[str, object] | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": 1,
        "event_id": str(uuid4()),
        "event_type": event_type,
        "occurred_at": utc_now_iso(),
        "sequence": sequence,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "ticket_id": ticket_id,
        "status": status,
        "executor_version": executor_version,
    }
    if repo_head is not None:
        event["repo_head"] = repo_head
    if payload is not None:
        event["payload"] = payload
    if error is not None:
        event["error"] = error
    return event


def _with_validation_events(
    execution_result: ProviderExecutionResult,
    validation_decision: ValidationDecision,
) -> ProviderExecutionResult:
    validation_error = _validation_error_payload(validation_decision)
    validation_events = list(execution_result.events)
    validation_events.append(
        _dispatcher_event(
            event_type="validation.completed",
            status="succeeded" if validation_decision.decision == "accepted" else "failed",
            run_id=execution_result.attempt_summary["run_id"],
            attempt_id=execution_result.attempt_summary["attempt_id"],
            ticket_id=execution_result.attempt_summary["ticket_id"],
            executor_version="phase-1",
            repo_head=None,
            sequence=len(validation_events),
            payload={
                "decision": validation_decision.decision,
                "reason": validation_decision.reason,
                "diagnostics": list(validation_decision.diagnostics),
            },
            error=validation_error,
        )
    )
    validation_events.append(
        _dispatcher_event(
            event_type="write_gate.decided",
            status="succeeded" if validation_decision.decision == "accepted" else "failed",
            run_id=execution_result.attempt_summary["run_id"],
            attempt_id=execution_result.attempt_summary["attempt_id"],
            ticket_id=execution_result.attempt_summary["ticket_id"],
            executor_version="phase-1",
            repo_head=None,
            sequence=len(validation_events),
            payload={
                "decision": validation_decision.decision,
                "reason": validation_decision.reason,
                "changed_paths": list(validation_decision.changed_paths),
                "requires_human_review": validation_decision.requires_human_review,
            },
            error=validation_error,
        )
    )
    return replace(execution_result, events=tuple(validation_events))


def _validation_error_payload(validation_decision: ValidationDecision) -> dict[str, object] | None:
    if validation_decision.decision == "accepted":
        return None
    return {
        "kind": "validation",
        "message": validation_decision.reason,
        "retryable": validation_decision.decision == "handoff_required",
    }