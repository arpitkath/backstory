# Demo: The Subscription Bug That Would Have Struck Twice

## The Setup

A subscription billing webhook had two bugs:
- It wasn't updating `next_due_on` after successful charges
- It was cancelling subscriptions on failed payments instead of marking them as pending

## The Fix

Claude Code was asked to fix it. The session was captured with Backstory.

## Before / After

### `app/api/webhooks/razorpay/route.ts` (before)

```typescript
export async function POST(req: Request) {
  const event = await validateWebhook(req)
  if (event.type === 'subscription.charged') {
    // TODO: update next billing date
    return Response.json({ ok: true })
  }
  if (event.type === 'payment.failed') {
    await db.subscription.update({
      where: { id: event.subscription_id },
      data: { status: 'cancelled' }
    })
  }
}
```

### `app/api/webhooks/razorpay/route.ts` (after)

```typescript
export async function POST(req: Request) {
  const event = await validateWebhook(req)
  if (event.type === 'subscription.charged') {
    await db.subscription.update({
      where: { id: event.subscription_id },
      data: { next_due_on: calculateNextDue(event) }
    })
    return Response.json({ ok: true })
  }
  if (event.type === 'payment.failed') {
    // Don't cancel — mark as pending so retry logic handles it
    await db.subscription.update({
      where: { id: event.subscription_id },
      data: { status: 'pending' }
    })
  }
}
```

## Three Weeks Later

A teammate sees a new payment failure and wonders: "Should I cancel this subscription right now?"

Instead of guessing, they run:

```bash
backstory why HEAD~3
```

And get back:

```
Commit: 8f21c9a
Message: Fix subscription renewal handling
Agent: Claude Code

Why this changed:
  The webhook handler was not updating the next billing date after
  successful recurring charges. Failed payments were not separated
  from cancellations.

Key decisions:
  - subscription.charged updates next_due_on
  - payment.failed marks subscription as pending, not cancelled
  - webhook handling must be idempotent

Risks:
  - Idempotency depends on storing Razorpay event IDs
  - Existing subscriptions need a next_due_on backfill
```

**The teammate now knows: don't cancel — mark as pending. The original reasoning is preserved.**

## What Backstory Made Possible

Without Backstory, the teammate would have to:
1. Read the diff (shows what, not why)
2. Search Slack/Linear for context
3. Ask the original developer

With Backstory: one command.
