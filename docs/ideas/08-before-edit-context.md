# `backstory before-edit`

## Priority

P0

## Idea

Provide important prior context before a developer or AI agent edits a file.

## Command

```bash
backstory before-edit app/api/webhooks/razorpay/route.ts
```

## Example Output

```text
Before editing this file, know this:

- Do not treat payment.failed as cancellation.
- Verify Razorpay webhook signature before DB updates.
- Keep webhook handling idempotent.
- next_due_on is updated only after successful recurring charge.
- Existing users may need backfill when billing fields change.
```

## Rationale

This turns Backstory from an archive into a context provider.
