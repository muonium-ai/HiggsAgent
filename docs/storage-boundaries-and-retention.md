# Storage Boundaries and Retention

## Storage Boundary

HiggsAgent separates committed repository artifacts from local execution artifacts.

### Committed Artifacts

- validated project outputs
- schemas and configuration
- documentation
- tests and fixtures
- sanitized summaries only when explicitly approved

### Local-Only Artifacts

- raw prompts
- raw model responses
- provider payloads and headers
- tool stdout and stderr
- temporary execution artifacts
- full event streams and debug traces

## Recommended Local Layout

- `.higgs/local/runs/<run_id>/<attempt_id>/events.ndjson`
- `.higgs/local/runs/<run_id>/<attempt_id>/artifacts/`
- `.higgs/local/analytics/attempt-summaries.ndjson`
- `.higgs/local/analytics/aggregates/<window>.ndjson`
- `.higgs/local/analytics/exports/<generated_at>.json`

These paths are intentionally ignored by version control.

## Redaction Rules

- Treat prompts, responses, headers, env values, and credentials as sensitive by default.
- Persist references plus hashes where possible instead of duplicating raw content.
- If a secret is detected after persistence, replace the raw artifact with a tombstone record and keep only the metadata needed for audit.

## Retention Defaults

- Raw prompts, raw responses, and provider payloads: 14 days local-only
- Tool stdout and stderr: 14 days local-only
- Event streams and normalized attempt summaries: 90 days local-only
- Local aggregate analytics snapshots: 90 days local-only by default
- Sanitized aggregate analytics exports: longer retention if they contain no raw or secret-bearing content

## Write Policy Interaction

Phase 1 should not commit raw telemetry automatically. Only validated repository outputs may cross from local execution storage into committed project state.