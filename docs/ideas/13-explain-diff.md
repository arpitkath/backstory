# `backstory explain-diff`

## Priority

P1

## Idea

Explain the current diff before commit.

## Command

```bash
backstory explain-diff
```

## Example Output

```text
Current diff summary:
- Adds handling for subscription.halted.
- Updates subscription status mapping.
- Adds next_due_on update.

Why based on current AI session:
The user wanted blocked/stopped payments to be handled without immediately deleting Pro access.

Potential issues:
- No test added for halted subscription.
- Existing event idempotency logic not updated.
```

## Rationale

This helps developers catch missing tests, risks, and rationale gaps before commit.
