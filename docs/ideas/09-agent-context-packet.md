# Agent Context Packet

## Priority

P1

## Idea

Create a compact output format for another AI agent to consume before editing code.

## Command

```bash
backstory context-pack app/api/webhooks/razorpay/route.ts
```

## Example Output

```md
## Relevant AI Memory

You are editing `app/api/webhooks/razorpay/route.ts`.

Prior decisions:
1. `payment.failed` should mark subscription as pending, not cancelled.
2. `subscription.cancelled` revokes Pro access.
3. `subscription.charged` updates `next_due_on`.
4. Webhook handling must be idempotent.

Do not break:
- Signature verification before processing.
- Event deduplication.
- Existing subscription state transitions.
```

## Rationale

This can later connect through MCP, but the first version can remain a CLI command.
