# HiggsAgent Architecture

## Purpose

HiggsAgent is a Git-native dispatcher that routes work tickets to different model providers based on structured ticket semantics. The system is intentionally white-box: routing decisions, execution metadata, tool-call behavior, retries, cost, and timing must all be inspectable.

This document defines the initial architecture direction used to create the backlog. It is not a full implementation spec, but it establishes the contracts and sequencing needed to build the project safely with multiple agents.

## Current State

- The repository currently contains the product PRD and a MuonTickets board.
- There is no product runtime code yet.
- The first implementation work must therefore create foundation contracts before dispatcher code begins.

## System Goals

- Scan MuonTickets tickets and identify executable work.
- Normalize ticket semantics into routing signals.
- Route work deterministically in Phase 1.
- Execute through hosted providers first, then hybrid hosted and local providers in later phases.
- Enforce guardrails before repository writes.
- Record execution events for observability, analytics, and later adaptive routing.
- Support open-source operation across many projects using multiple agents.

## High-Level Pipeline

1. Ticket discovery
2. Eligibility and dependency checks
3. Semantic classification
4. Routing decision
5. Provider execution
6. Tool-call handling
7. Output validation
8. Repository write or review handoff
9. Event logging and analytics export

## Foundation Decisions Required Before Feature Work

### Runtime and Tooling

The PRD states that the initial runtime will be PHP while also referencing `uv`. That combination is not yet an operational contract. The foundation phase must define:

- how the PHP runtime is installed and invoked
- whether `uv` is only used for auxiliary tooling, ticket automation, and tests
- how local development, CI, and packaging work
- what can be considered stable for open-source contributors

### Repository Structure

The repo should separate shared hotspots from isolated work areas so multiple agents can contribute safely. A likely direction is:

- `src/` for core dispatcher logic
- `src/Providers/` or equivalent for provider adapters
- `config/` for routing and guardrail configuration
- `schemas/` for Higgs-specific ticket and event contracts
- `tests/` for unit, integration, and simulation coverage
- `docs/` for contributor, operator, and architecture docs

This structure is intentionally provisional until the runtime/tooling contract is finalized.

### Ticket Semantics Contract

The PRD introduces routing inputs such as platform and complexity, but the current MuonTickets template only includes generic workflow fields. HiggsAgent needs an explicit semantic contract that defines:

- required routing inputs
- optional routing hints
- defaults and normalization rules
- compatibility with the existing MuonTickets schema
- how invalid or incomplete semantics are handled

Without this contract, classifier and routing work will diverge quickly.

### Event and Observability Contract

Later phases depend on stable execution metadata. The event model must define:

- execution lifecycle stages
- prompt and response capture policy
- token, cost, timing, and tool-call fields
- failure and retry reasons
- what data can be committed versus retained locally
- retention and redaction rules for open-source use

### Guardrails and Repository Write Boundary

The PRD requires token, cost, timeout, and retry limits, but the write boundary is the more critical shared contract. HiggsAgent must decide early:

- when changes may be written to the repository
- whether autonomous commits are allowed
- when human review is mandatory
- how validation failures are surfaced
- how secrets, prompts, and provider artifacts are kept out of version control

## Dependency Model

### Phase Dependencies

- Phase 0 Foundation blocks all feature phases.
- Phase 1 Deterministic Dispatcher depends on the foundation contracts.
- Phase 2 Analytics depends on the Phase 1 event model and execution outputs.
- Phase 3 Hybrid Execution depends on stable executor interfaces from Phase 1 and reuses analytics signals from Phase 2.
- Phase 4 Adaptive Dispatch depends on normalized telemetry from Phase 2 and multi-provider behavior from Phase 3.
- Phase 5 Benchmarking depends on provider abstractions, event schemas, and normalized result formats from earlier phases.

### Swarm Isolation

Good parallel work after interfaces are stable:

- documentation
- test fixture creation
- test coverage expansion
- provider adapters behind fixed interfaces
- dashboard or reporting views
- benchmark report generation

High-coordination work that should be serialized or tightly owned:

- ticket semantic schema
- routing rules
- provider execution boundary
- output validation and write gate
- shared event schema
- global configuration surfaces

## Testing Strategy

Testing must be planned as first-class work in every phase.

### Phase 0

- define the CI matrix
- define contract validation strategy
- define smoke-test expectations for early runtime scaffolding

### Phase 1

- unit tests for scanning, classification, and routing
- integration tests for the deterministic execution pipeline
- failure-path tests for retries, timeouts, and validation rejects

### Phase 2+

- analytics correctness checks
- fallback and provider failure drills
- scoring regression tests
- benchmark reproducibility checks

## Documentation Strategy

Documentation must ship alongside interfaces, not after implementation.

- contributor docs for setup and development workflow
- operator docs for execution, monitoring, and budgets
- architecture docs for routing, guardrails, and observability
- methodology docs for analytics, adaptive routing, and benchmarking

## Open-Source Requirements

This project is expected to support many projects and many agents. That changes the design baseline:

- contributor onboarding must be explicit and reproducible
- guardrails must be documented, not implicit
- log and artifact retention must avoid leaking secrets or prompts by default
- interfaces and schemas must be stable enough for independent agent work
- swarm-safe task boundaries must be encoded into the backlog using dependencies

## Recommended Backlog Shape

Implement in this order:

1. Phase 0 foundation contracts and documentation
2. Phase 1 deterministic dispatcher MVP
3. Re-evaluate downstream decomposition after the Phase 0 contracts are accepted

The repository should not start coding the dispatcher core before the architecture contracts above are captured in tickets and resolved.