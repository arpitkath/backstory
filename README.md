# Backstory

Backstory is a local-first memory layer for AI-assisted coding. It captures
session context, stores the durable record as OKF markdown, links that memory
to Git commits, and helps answer why code changed later.

## What It Does

- Captures AI coding sessions
- Stores the persisted session record in `.backstory/knowledge/sessions/`
- Attaches sessions to commits
- Explains commits, files, lines, ranges, and diffs with Git-backed context
- Surfaces contradiction warnings for new changes that appear to reverse prior
  decisions

## Quick Start

```bash
backstory init
backstory dump
git add .
git commit -m "..."
backstory why HEAD
```

If your AI tool writes a local transcript file, you can point Backstory at it:

```bash
backstory dump --agent claude --transcript ./transcript.md
```

## Main Commands

- `backstory init`
- `backstory dump`
- `backstory attach HEAD`
- `backstory why HEAD`
- `backstory show <session>`
- `backstory search <query>`
- `backstory file <path>`
- `backstory line <path>:<line>`
- `backstory range <path>:<start>-<end>`
- `backstory code <path>:<start>-<end>`
- `backstory diff`
- `backstory status`
- `backstory redact`

## Storage Layout

Backstory stores session memory in OKF markdown files:

```text
.backstory/
  config.json
  index.sqlite
  knowledge/
    index.md
    sessions/
      index.md
      latest.md
      sha256-<session>.md
  redactions/
    tombstones.log
```

## Integration

Backstory works with Claude, Codex, Cursor, and other AI tools as long as they
can leave a local transcript file or a commit-diff trail. It does not require a
hosted service or extension to be useful.

## Documentation

- [Engineering walkthrough](docs/engineering-walkthrough.md)
- [Product spec](docs/prd.md)
- [Retrieval model](docs/retrieval.md)

