"""Minimal deterministic dispatcher orchestration for Phase 1 integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    guardrails_path: Path,
    write_policy_path: Path,
    planned_changes: tuple[ProposedFileChange, ...],
    validation_summary: str,
    tool_invoker=None,
    diff_is_deterministic: bool = True,
    run_id: str = "run-1",
    attempt_id: str = "attempt-1",
    repo_head: str | None = None,
) -> DispatchOutcome | None:
    """Run the current Phase 1 dispatcher pipeline for the next ready ticket."""

    from higgs_agent.providers.hosted import OpenRouterExecutor, load_executor_limits
    from higgs_agent.routing import choose_route, classify_ticket, load_route_guardrails
    from higgs_agent.validation import ValidationInput, evaluate_write_request, load_write_policy

    scan_result = scan_ticket_directory(tickets_dir)
    ticket = select_next_ready_ticket(scan_result)
    if ticket is None:
        return None

    semantics = classify_ticket(ticket)
    route = choose_route(semantics, load_route_guardrails(guardrails_path))
    executor = OpenRouterExecutor(
        limits=load_executor_limits(guardrails_path),
        transport=transport,
    )
    execution_input = ExecutorInput(
        ticket_id=ticket.id,
        run_id=run_id,
        attempt_id=attempt_id,
        route=route,
        prompt=_build_prompt(ticket),
        system_prompt="You are HiggsAgent.",
        repo_head=repo_head,
        allow_tool_calls=route.requires_tool_calls,
    )
    execution_result = executor.execute(execution_input, tool_invoker=tool_invoker)

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

    return DispatchOutcome(
        ticket=ticket,
        semantics=semantics,
        route=route,
        execution_result=execution_result,
        validation_decision=validation_decision,
    )


def _build_prompt(ticket: TicketRecord) -> str:
    title = ticket.frontmatter.get("title", ticket.id)
    body = ticket.body.strip()
    if not body:
        return str(title)
    return f"{title}\n\n{body}"