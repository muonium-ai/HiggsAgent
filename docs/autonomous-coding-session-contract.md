# Autonomous Coding Session Contract

## Purpose

This document defines the normalized contract for autonomous single-ticket coding sessions in HiggsAgent. It specifies the session state, action model, mutation inference rules, validation evidence flow, and MuonTickets workflow behavior that Phase 6 implementations must follow.

## Goal

The autonomous coding session contract makes OpenRouter-backed coding execution inspectable, testable, and policy-controlled.

It is successful when HiggsAgent can turn a coding-model interaction into a bounded sequence of repository reads, directory creation, file creation, patch application, command execution, validation evidence, and workflow state changes without relying on hand-authored changed-file or validation-summary inputs.

## Required Inputs

Autonomous coding sessions may rely only on the existing repository contracts plus explicit operator inputs:

- repository root
- tickets directory
- requirements or project context inputs
- guardrails and write-policy configuration
- OpenRouter credentials and model selection inputs
- bounded validation command configuration

## Session Model

### 1. Session Scope

- One autonomous coding session corresponds to one ticket attempt.
- A session may contain multiple model turns and multiple tool or action steps.
- Session state must remain attributable to a single `run_id`, `attempt_id`, and `ticket_id`.

### 2. Normalized Action Types

The coding-session abstraction must normalize provider-specific output into explicit action records.

Required action categories:

- `prompt.rendered`: the synthesized prompt or prompt reference used for the coding turn
- `workspace.read`: file or directory inspection performed by the runtime
- `directory.create`: creation of one or more directories
- `file.write`: creation or replacement of full file contents
- `file.patch`: structured modification of existing file contents
- `command.run`: bounded shell or validation command execution
- `ticket.workflow`: MuonTickets lifecycle operations such as claim, comment, and status transition
- `session.note`: human-readable reasoning, summary, or handoff text captured as an artifact instead of hidden provider state

Optional action categories may be added later, but every category must map cleanly onto inspectable workspace or workflow effects.

### 3. Action Record Requirements

Each normalized action record must include:

- `action_id`
- `action_type`
- `sequence`
- `status`
- `ticket_id`
- `run_id`
- `attempt_id`

Common optional fields include:

- `path` or `paths`
- `command`
- `exit_code`
- `stdout_artifact_ref`
- `stderr_artifact_ref`
- `diff_artifact_ref`
- `payload_summary`
- `error_kind`
- `error_detail`

Provider-specific raw payloads may be retained as local artifacts, but they must not be required to understand what the session did.

## Workspace Mutation Inference

### 1. Source Of Truth For Changed Paths

- HiggsAgent must derive changed paths from the observed action stream and resulting workspace state, not from operator-entered CLI flags.
- `directory.create`, `file.write`, and `file.patch` actions are the authoritative mutation sources.
- Validation commands may add derived evidence but must not redefine which files changed.

### 2. Mutation Classification

Every changed path should be classified as one of:

- `created`
- `modified`
- `deleted`
- `binary_modified`
- `directory_created`

If exact additions and deletions are available, HiggsAgent should derive them from workspace diffs after action application. If exact line counts are unavailable, the runtime must emit explicit partial metadata rather than fabricated counts.

### 3. Materialization Rules

- Scaffold-style responses may create nested directories and new files in one bounded session.
- Patch-style responses may update only files that exist at the time the patch is applied unless the patch explicitly encodes file creation.
- Ambiguous or malformed materialization instructions must fail safely with actionable error output.

## Validation Evidence Contract

### 1. Validation Inputs

- Validation commands must come from explicit operator or policy configuration.
- HiggsAgent must record which validation commands ran, in what order, and with what exit status.
- Validation commands must execute against the actual mutated workspace state.

### 2. Validation Evidence Output

Validation evidence must include:

- command string or configured validation step identifier
- exit code
- normalized result (`passed`, `failed`, `timed_out`, `blocked`)
- stdout and stderr artifact references when output exists
- a short evidence summary suitable for write-gate and review output

### 3. Validation Summary Generation

- The runtime may synthesize a normalized validation summary from one or more validation steps.
- The summary must be derived from actual command results rather than freeform operator text.
- Failed validation must remain visible to the write gate and may not be collapsed into success.

## MuonTickets Workflow Rules

### 1. Claim Behavior

- Autonomous single-ticket execution may claim a ticket automatically only when the ticket is `ready` and dependency-unblocked.
- The claim must flow through MuonTickets commands rather than frontmatter mutation.
- If claim fails, the session must stop before repository mutation begins.

### 2. Progress Commentary

- HiggsAgent may emit progress comments through MuonTickets at bounded checkpoints such as session start, validation failure, and review handoff.
- Comments must summarize operator-relevant progress rather than provider-internal reasoning logs.

### 3. Status Transition Rules

- Successful autonomous runs may transition the ticket to `needs_review`.
- Validation failure, policy block, secret-suspect output, or ambiguous diffs must not auto-transition the ticket to `done`.
- Blocked runs should record handoff context and leave the workflow state reviewable rather than silently reverting or forcing completion.

## Operator Controls And Policy Extensions

Phase 6 autonomous sessions introduce these control-plane expectations:

- `autonomous_execution.enabled`: whether the runtime may execute autonomous coding sessions at all
- `autonomous_execution.max_session_steps`: maximum normalized action count per ticket attempt
- `autonomous_execution.allowed_command_profiles`: which command categories the coding session may run
- `autonomous_execution.validation_commands`: explicit validation steps to run after workspace mutation
- `autonomous_execution.materialization_formats`: allowed response shapes such as scaffold writes and structured patch application
- `autonomous_execution.auto_claim`: whether HiggsAgent may claim ready tickets automatically
- `autonomous_execution.auto_comment`: whether HiggsAgent may emit MuonTickets progress comments automatically
- `autonomous_execution.auto_transition_to_needs_review`: whether successful runs may advance tickets without manual workflow commands
- `autonomous_execution.create_local_commit`: whether local commits may be created after successful review-mode execution

These are contract-level fields for the Phase 6 implementation. They do not imply that every field is already implemented in the current runtime.

## Failure Classes

Autonomous coding sessions must normalize failures into actionable categories:

- `provider_failure`
- `materialization_failure`
- `validation_failure`
- `policy_block`
- `secret_suspect`
- `workflow_failure`
- `coordination_failure`

Each failure must be represented both in action-level output and in the terminal attempt summary.

## Review And Handoff Expectations

- Every autonomous coding session must produce enough artifacts to review the attempted workspace changes and validation evidence.
- Handoff artifacts should summarize changed paths, validation status, workflow status, and the blocking reason when the session cannot complete cleanly.
- Raw prompts and provider payloads remain local-only unless an explicit retention-safe contract says otherwise.

## Normative Sources

- [phase-6-autonomous-ticket-execution.md](phase-6-autonomous-ticket-execution.md)
- [runtime-tooling.md](runtime-tooling.md)
- [safety-model.md](safety-model.md)
- [observability-contract.md](observability-contract.md)
- [secret-handling.md](secret-handling.md)