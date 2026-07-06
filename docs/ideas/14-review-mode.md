# Review Mode

## Priority

P1

## Idea

Add reviewer-focused commit context.

## Command

```bash
backstory review HEAD
```

## Example Output

```text
Reviewer notes:
- This was AI-assisted.
- Main decision: separate failed payment from cancellation.
- Tests run: npm run lint.
- Missing test: duplicate webhook event.
- Risk: old subscriptions may not have next_due_on.
```

## Rationale

The command should answer "What should a human reviewer know about this AI-assisted commit?"
