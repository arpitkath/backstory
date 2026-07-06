# Retention And Pruning

## Priority

P2

## Idea

Add a configurable retention policy so local storage does not silently grow forever.

## Example Policy

```text
Auto-prune raw sessions older than 90 days.
Keep summaries forever.
```

## Rationale

This should be reconciled with the OKF source-of-truth model before implementation, especially if raw transcripts are not persisted.

