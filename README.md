# Backstory

Backstory is a local-first memory layer for AI-assisted coding. It helps
developers recover why a decision was made later, after the codebase and the
conversation have both moved on in a fast-changing environment. It captures
session context, stores the durable record as OKF (Open Knowledge Format;
[Google Cloud announcement](https://cloud.google.com/blog/products/data-analytics))
markdown, and links that memory to Git commits so the reasoning stays
searchable. It also supports contradiction detection so later changes that
appear to reverse earlier decisions can be surfaced quickly.

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
backstory why HEAD
```

Capture is expected to happen inside the AI tool through its own hook or
lifecycle callback. Backstory then ingests the session internally:

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

Backstory is designed for tool-native integration with Claude, Codex, Cursor,
and similar AI tools. The preferred path is a tool-specific hook, callback, or
transcript exporter that hands the session to Backstory automatically. `dump`
is the ingestion step, not the primary user workflow. Git remains the linkage
layer for commits, not the capture layer.

## Documentation

- [Engineering walkthrough](docs/engineering-walkthrough.md)
- [Product spec](docs/prd.md)
- [Retrieval model](docs/retrieval.md)
