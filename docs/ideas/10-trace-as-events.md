# Trace As Events

## Priority

P1

## Idea

Represent sessions as factual event timelines rather than only chat text.

## Example

```json
[
  {
    "type": "user_prompt",
    "content": "Fix subscription renewal handling"
  },
  {
    "type": "file_read",
    "path": "app/api/webhooks/razorpay/route.ts"
  },
  {
    "type": "file_edit",
    "path": "lib/subscription.ts",
    "hunk": "..."
  },
  {
    "type": "command",
    "command": "npm run lint",
    "status": "success"
  },
  {
    "type": "decision",
    "content": "Do not cancel user immediately on payment.failed"
  }
]
```

## Rationale

Event traces connect prompts, tool calls, evidence, actions, commands, and decisions more usefully than raw transcript storage.

