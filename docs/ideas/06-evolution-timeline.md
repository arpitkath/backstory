# Evolution Timeline

## Priority

P0

## Idea

Show how reasoning changed across commits for code that has evolved over time.

## Example

```text
Evolution of this code:

1. Initial implementation
   Added basic subscription webhook handling.

2. Payment failure handling
   Decided payment.failed should move subscription to pending, not cancel.

3. Renewal fix
   Added next_due_on update after subscription.charged.

4. Current behavior
   subscription.cancelled is now the only event that revokes Pro access.
```

## Rationale

Old AI reasoning may be outdated. Backstory should explain the timeline instead of returning only the oldest or latest memory.

