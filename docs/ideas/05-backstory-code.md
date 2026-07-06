# `backstory code`

## Priority

P0

## Idea

Add a command that explains why a specific code block exists.

## Command

```bash
backstory code app/api/webhooks/razorpay/route.ts:90-150
```

## Inputs To Combine

- `git blame`
- `git log --follow`
- Patch history
- Linked AI sessions
- Code memory cards
- Prior session summaries

## Expected Output

The command should answer "Why is this code written this way?", not only "Which commit changed this?"
