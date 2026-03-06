# Ticket Semantics Contract

## Purpose

MuonTickets remains the workflow envelope for HiggsAgent, but Higgs requires a small set of additional frontmatter keys so classification and routing remain deterministic across projects and agents.

## Rules

- MuonTickets fields remain authoritative for workflow state.
- Higgs adds flat frontmatter keys rather than a nested object.
- Unknown labels and tags must not be treated as substitutes for required Higgs routing fields.
- The classifier should normalize missing optional Higgs fields using the rules below.

## Higgs Fields

| Field | Required | Allowed values | Default | Meaning |
| --- | --- | --- | --- | --- |
| `higgs_schema_version` | yes | `1` | `1` | Locks the semantic contract used by the classifier and router. |
| `higgs_platform` | yes | `agnostic`, `web`, `ios`, `macos`, `android`, `linux`, `windows`, `cross_platform`, `repo` | `agnostic` | Primary platform or execution surface. |
| `higgs_complexity` | no | `low`, `medium`, `high` | derived from `effort` or `medium` in templates | Complexity hint for model tier selection. |
| `higgs_execution_target` | no | `auto`, `hosted`, `local` | `auto` | Preference for hosted versus local execution. |
| `higgs_tool_profile` | no | `none`, `standard`, `extended` | `standard` | Coarse tool-use profile. |

## Mapping to MuonTickets Fields

| MuonTickets field | Higgs use |
| --- | --- |
| `type` | Primary workload class and first routing input. |
| `priority` | Dispatch urgency. |
| `effort` | Fallback signal for complexity normalization. |
| `labels` | Secondary routing hints only. |
| `tags` | Freeform metadata, not required for correctness. |
| `status`, `depends_on`, `owner` | Workflow controls, not semantic routing inputs. |

## Validation Expectations

- `higgs_schema_version` must match the current contract.
- `higgs_platform` must be present and use a known enum value.
- `higgs_complexity` may be omitted, but if present it must use a known enum value.
- `higgs_execution_target=local` should be treated as non-routable until hybrid execution is implemented.
- `higgs_tool_profile` constrains executor capabilities and should be enforced by policy rather than ignored.

## Example Frontmatter

```yaml
type: code
priority: p0
effort: m
higgs_schema_version: 1
higgs_platform: ios
higgs_complexity: high
higgs_execution_target: hosted
higgs_tool_profile: extended
```