# Simple Integration Contract

## Priority

P0

## Idea

Keep the MVP integration contract simple enough for any tool to call the CLI.

## Commands

```bash
backstory dump --transcript <path> --agent claude
backstory dump --transcript <path> --agent codex
backstory dump --stdin
```

## Rationale

Tool-specific hooks and extensions can come later. The first integration surface should be stable, scriptable, and easy to adopt.
