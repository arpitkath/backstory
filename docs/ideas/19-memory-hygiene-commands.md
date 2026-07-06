# Memory Hygiene Commands

## Priority

P1

## Idea

Add maintenance commands so local storage stays trustworthy.

## Commands

```bash
backstory doctor
backstory gc
backstory prune --older-than 90d
backstory repair
```

## Use Cases

- Fix broken commit-session links.
- Remove orphan sessions.
- Compress old sessions.
- Rebuild index.
- Detect missing Git notes.
- Detect sessions not attached to commits.

## Rationale

Developers will abandon Backstory if storage becomes messy or silently inconsistent.
