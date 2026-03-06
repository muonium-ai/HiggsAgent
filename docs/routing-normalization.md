# Routing Normalization Rules

## Purpose

The classifier and router need deterministic normalization rules so later implementation tickets do not reinterpret missing values differently.

## Normalization

### `higgs_schema_version`

- Missing value during transition: normalize to `1` and emit a validation warning.
- Long-term rule: require `1` explicitly in new tickets.

### `higgs_platform`

- Missing value: normalize to `agnostic`.
- Unknown value: reject as invalid.

### `higgs_complexity`

- Explicit value wins if valid.
- If omitted, derive from `effort`:
  - `xs` or `s` -> `low`
  - `m` -> `medium`
  - `l` -> `high`
- If both are absent or unusable, normalize to `medium` and emit a warning.

### `higgs_execution_target`

- Missing value: normalize to `auto`.
- `local` remains non-routable in Phase 1 and must surface a clear validation or routing block.

### `higgs_tool_profile`

- Missing value: normalize to `standard`.
- `none` means the executor should avoid tool calls entirely.
- `extended` only permits tool use if the active guardrail policy allows it.

## Phase 1 Routing Interpretation

- `type` chooses the broad model family or prompt strategy.
- `higgs_platform` refines platform-sensitive routing.
- `higgs_complexity` influences the model tier.
- `priority` influences dispatch order, not semantic class.
- `higgs_execution_target` is an execution constraint.
- `higgs_tool_profile` informs executor capability limits.

## Anti-Rules

- Do not infer `higgs_platform` from labels.
- Do not treat tags as required routing inputs.
- Do not silently downgrade `local` execution requests to `hosted` in Phase 1.