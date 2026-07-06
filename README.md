# Backstory

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![OKF](https://img.shields.io/badge/knowledge%20format-OKF-orange)](https://cloud.google.com/blog/products/data-analytics)

**Git shows what changed. Backstory shows why.**

Backstory preserves the decision-making process behind AI-assisted code
changes, not just the diff or a pile of comments.

- Recovers why a decision was made later, after the codebase has moved on
- Stores durable session memory as OKF (Open Knowledge Format) markdown
- Links that memory to Git commits so the reasoning stays searchable
- Detects contradictions when later changes appear to reverse earlier decisions
- Connects code to the decision-making process, not just to chat logs

## Example

You ask an AI agent to fix subscription renewal logic.

Later, you can ask:

```bash
backstory why HEAD
```

And get back something like:

```text
Commit: 8f21c9a
Message: Fix subscription renewal handling
Agent: Claude Code

Why this changed:
  The webhook handler was not updating the next billing date after
  successful recurring charges. Failed payments were not separated
  from cancellations.

Key decisions:
  - subscription.charged updates next_due_on
  - payment.failed marks subscription as pending, not cancelled
  - webhook handling must be idempotent

Files changed:
  - app/api/webhooks/razorpay/route.ts
  - lib/subscription.ts

Risks:
  - Idempotency depends on storing Razorpay event IDs
  - Existing subscriptions need a next_due_on backfill
```

That is the useful part: not just what changed, but why it changed.

## Contradiction Detection

Backstory also watches for new changes that appear to reverse earlier recorded
decisions.

```text
⚠ This change may contradict a decision from commit 8f21c9a:
  "payment.failed should mark subscription as pending, not cancelled"
```

That turns the tool from an archive into a guardrail.

## What Backstory Does

- Captures AI coding session context
- Extracts durable decisions, risks, follow-ups, and changed files
- Stores memory as OKF-style markdown under `.backstory/knowledge/`
- Links session memory to Git commits
- Retrieves context by commit, file, line, range, or current diff
- Warns when a new change appears to contradict an earlier decision
- Keeps raw transcript persistence out of the durable storage path

Backstory is not an AI coding agent. It is the memory layer around
AI-assisted coding.

## Quick Start

```bash
backstory init
backstory why HEAD
```

Backstory is designed for tool-native capture. The AI tool should hand session
context to Backstory through its own hook, callback, or transcript exporter.
Backstory then ingests that session internally.

If you need to import a transcript export directly:

```bash
backstory dump --agent claude --transcript ./transcript.md
```

## Core Commands

| Command | What it does |
|---|---|
| `backstory init` | Set up Backstory in the current repo |
| `backstory dump` | Ingest an AI session into OKF markdown |
| `backstory attach HEAD` | Link a session to a commit |
| `backstory why HEAD` | Explain why a commit happened |
| `backstory show <session>` | View a stored session |
| `backstory search <query>` | Search past sessions and decisions |
| `backstory file <path>` | Show AI context relevant to a file |
| `backstory line <path>:<line>` | Show the decision behind a specific line |
| `backstory range <path>:<start>-<end>` | Show context for a range of lines |
| `backstory code <path>:<start>-<end>` | Show why a code block exists |
| `backstory diff` | Explain the reasoning behind the current diff |
| `backstory status` | Show Backstory state in this repo |
| `backstory redact` | Re-scan and redact sensitive data from stored sessions |

## How It Works

1. A tool-native hook, callback, or transcript exporter captures the session.
2. Backstory ingests the session into OKF markdown.
3. The session is attached to the relevant Git commit.
4. Later, you query the commit, file, line, range, or diff.

Git stays the linkage layer. Backstory stores the reasoning.

## Storage

Backstory stores local project memory under `.backstory/`:

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

Session memory is stored as OKF-style markdown so it stays human-readable,
Git-friendly, and agent-friendly.

## Privacy

Backstory is local-first.

- No cloud service is required
- No telemetry is required
- Session memory stays inside the repository
- Raw transcripts are not persisted as the durable session record
- Backstory stores extracted decisions, risks, follow-ups, changed files, and
  Git context

## Integration

Backstory is designed for tool-native integration with Claude, Codex, Cursor,
and similar AI tools.

The preferred path is a tool-specific hook, callback, or transcript exporter
that hands the session to Backstory automatically. `dump` exists as the
ingestion step, not the primary workflow.

## Documentation

- [Engineering walkthrough](docs/engineering-walkthrough.md)
- [Product spec](docs/prd.md)
- [Retrieval model](docs/retrieval.md)

