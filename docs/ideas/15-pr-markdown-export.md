# PR Markdown Export

## Priority

P1

## Idea

Generate pull-request-ready markdown from local Backstory context without requiring a dashboard.

## Command

```bash
backstory pr-note HEAD
```

## Example Output

```md
## AI Context

This commit was created with AI assistance.

### Why

...

### Key decisions

...

### Risks

...
```

## Rationale

This gives teams PR context while preserving CLI-first and local-first positioning.
