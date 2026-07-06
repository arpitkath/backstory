# Why Confidence

## Priority

P1

## Idea

Show confidence for generated explanations.

## Example

```text
Confidence: High
Reason: Exact line was last changed by commit 8f21c9a, which has attached AI memory.

Confidence: Medium
Reason: No exact line memory found, but related function was changed in 2 AI-assisted commits.

Confidence: Low
Reason: File changed before Backstory was installed.
```

## Rationale

Confidence makes Backstory more trustworthy by distinguishing direct knowledge from inference.

