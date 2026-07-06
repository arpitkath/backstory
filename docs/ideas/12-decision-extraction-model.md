# Decision Extraction Model

## Priority

P0

## Idea

Make decisions first-class records rather than incidental summary text.

## Fields

- Decision
- Reason
- Affected file/function
- Commit
- Status: active, superseded, conflicting, or unknown
- Evidence: transcript message, diff, or command

## Example

```json
{
  "decision": "payment.failed should not cancel subscription",
  "reason": "Failed payments may be retried before access is revoked",
  "file": "app/api/webhooks/razorpay/route.ts",
  "commit": "8f21c9a",
  "status": "active"
}
```

## Rationale

Structured decisions improve search, code-aware retrieval, contradiction detection, and before-edit context.

