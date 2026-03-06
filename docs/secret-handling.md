# Secret Handling

## Default Rule

Secrets must never enter committed project state through HiggsAgent execution artifacts.

## Allowed Secret Sources

- environment variables
- external secret stores

Tickets, prompts, docs, config examples, and committed logs are not secret sources.

## Sensitive Artifact Classes

- raw prompts
- raw model responses
- provider headers and payloads
- tool stdout and stderr
- environment values
- credentials and tokens

## Required Behavior

- Keep sensitive artifacts local-only by default.
- Redact or quarantine any output that appears to contain secrets.
- Commit sanitized summaries, not raw payloads.
- Stop repository writes immediately if secret-like material is detected in generated output.

## Protected Patterns

At minimum, the project should treat the following as protected:

- `.env*`
- API keys
- bearer tokens
- cookies and session identifiers
- SSH keys and private keys
- provider credential files

## Review Requirement

Any suspected secret leak requires human review before artifacts are retained or a ticket is marked complete.