# HiggsAgent Todo

## Immediate Work

1. Create the Phase 0 foundation epic: `T-000002`.
2. Define the runtime and tooling contract: `T-000003`.
3. Define repository structure and package boundaries: `T-000004`.
4. Define Higgs ticket semantics for routing: `T-000005`.
5. Define the execution event and observability schema: `T-000006`.
6. Define guardrails and the repository write policy: `T-000007`.
7. Define the initial test strategy and CI validation matrix: `T-000008`.
8. Define the initial contributor, operator, and architecture documentation skeleton: `T-000009`.

## Next Work

1. Create the Phase 1 deterministic dispatcher epic: `T-000010`.
2. Implement ticket scanning and ready-ticket selection: `T-000011`.
3. Implement semantic classification: `T-000012`.
4. Implement deterministic routing: `T-000013`.
5. Implement the provider execution boundary for OpenRouter: `T-000014`.
6. Implement output validation and repository write gating: `T-000015`.
7. Add unit and integration tests for the full Phase 1 path: `T-000016`.
8. Document the Phase 1 architecture and usage model: `T-000017`.

## Later Work

1. Phase 2 analytics and observability epic: `T-000018`.
2. Phase 3 hybrid hosted and local execution epic: `T-000019`.
3. Phase 4 adaptive dispatch epic: `T-000020`.
4. Phase 5 benchmarking mode epic: `T-000021`.
5. Phase 6 autonomous ticket execution epic: `T-000053`.
6. Phase 7 turnkey project build epic: `T-000058`.

## Ticket Creation Rules

1. Create tickets in dependency order.
2. Use `depends_on` for contract and shared-surface blockers.
3. Keep docs and tests as separate first-class tickets.
4. Parallelize only after interfaces are stable.
5. Validate the board after every creation batch.

## Swarm Safety Notes

Safe for isolated agents once contracts exist:

- docs
- tests
- fixtures
- provider adapters
- reporting views

Needs tighter coordination:

- routing semantics
- execution lifecycle
- write and validation gate
- shared schemas
- global config