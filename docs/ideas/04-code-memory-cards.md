# Code Memory Cards

## Priority

P0

## Idea

Generate file, function, or range-level memory cards for important code changes.

## Example

```text
Code: app/api/webhooks/razorpay/route.ts:handleWebhookEvent

Why this exists:
Handles Razorpay lifecycle events separately because failed payments, halted subscriptions, and cancellations have different product consequences.

Key decisions:
- payment.failed does not immediately remove Pro.
- subscription.cancelled removes Pro access.
- subscription.charged updates next_due_on.
- Webhook handling must be idempotent.

Relevant commits:
- 8f21c9a Fix subscription renewal handling
- 4ad93c1 Add Razorpay webhook verification

Risks:
- Duplicate events need idempotency protection.
- Old users may need backfill.
```

## Rationale

Future retrieval should not need to reparse full transcripts or broad summaries to explain a code block.

