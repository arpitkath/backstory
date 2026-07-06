# Adapter Architecture

## Priority

P0

## Idea

Add a normalized ingestion interface for transcript formats early.

## Rationale

Claude Code, Cursor, Copilot, Codex, Windsurf, and similar tools log differently. A plugin or adapter layer for transcript discovery and parsing will be cheaper to add now than to bolt on later.

## Expected Outcome

Each supported AI tool has a focused adapter that produces normalized Backstory events and decisions.

