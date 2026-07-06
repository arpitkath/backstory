# Superseded And Conflicting Memory

## Priority

P0

## Idea

Track whether memory items are active, superseded, conflicting, or unknown.

## Status Values

```text
active
superseded
conflicting
unknown
```

## Rationale

If one session says `payment.failed cancels subscription` and a later commit changes that behavior to `payment.failed only marks subscription pending`, the older reasoning should be marked as superseded by the later commit.

