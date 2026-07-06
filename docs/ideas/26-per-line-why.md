# Per-Line Why

## Priority

P2

## Idea

Extend why commands to line or hunk granularity, similar to `git blame` but for reasoning.

## Command

```bash
backstory blame lib/subscription.ts:42
```

## Rationale

Line-level reasoning is often more useful than commit-level lookup when a developer is investigating a specific behavior.
