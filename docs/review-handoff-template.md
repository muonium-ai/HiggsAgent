# Review Handoff Template

Use this structure when an automated run cannot safely complete without human review.

## Required Fields

- Ticket ID
- Run ID
- Attempt ID
- Changed paths
- Validation summary
- Guardrail usage summary
- Blocking reason
- Suggested next action

## Example

```text
Ticket ID: T-000015
Run ID: run-123
Attempt ID: attempt-1
Changed paths: src/Dispatcher.php, config/write-policy.example.json
Validation summary: tests passed, write gate blocked
Guardrail usage summary: tokens 8200/24000, cost 0.91/5.00, tool calls 3/8
Blocking reason: protected path touched and human review required
Suggested next action: review the write-policy change and approve or request revision
```