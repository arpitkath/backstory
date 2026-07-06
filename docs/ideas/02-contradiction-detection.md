# Contradiction Detection

## Priority

P0

## Idea

Warn when a new change appears to contradict a previously recorded decision in Backstory.

## Example

```text
Warning: This change contradicts a decision from commit 8f21c9a:
  "payment.failed should mark subscription as pending, not cancelled"
```

## Rationale

This turns Backstory from a passive archive into a regression-prevention tool.
