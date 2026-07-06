# Backstory

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![OKF](https://img.shields.io/badge/knowledge%20format-OKF-orange)](https://cloud.google.com/blog/products/data-analytics)

**Git shows what changed. Backstory shows why.**

Backstory preserves the decision-making process behind AI-assisted code
changes. It captures session context from AI coding tools, extracts the
durable reasoning (decisions, risks, alternatives), stores it as local
markdown, and links it to Git commits so you can retrieve the *why* later.

> **Why not just write good commit messages?**
> Commit messages describe what changed. They rarely capture the rejected
> alternatives, the risks you accepted, or the reasoning trail across a
> multi-step AI session. Backstory fills that gap: it stores the decision
> trail the AI tool produced, not just the final diff.

- Local-first by default — everything stays in your repo
- Recovers *why* a decision was made, after the codebase has moved on
- Stores durable session memory as OKF markdown — human-readable,
  Git-friendly, and agent-friendly
- Links memory to Git commits so the reasoning stays searchable
- Detects contradictions when later changes reverse earlier decisions
- Extracts decisions, risks, and follow-ups — not raw chat logs

Backstory is not an AI coding agent. It is the memory layer around
AI-assisted coding — useful whether you're building alone or shipping
across enterprise teams.

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

## What Gets Stored

Here is what that same session looks like on disk — only the extracted
reasoning, no raw conversation:

```markdown
---
type: Backstory Session
title: Fix subscription renewal handling
description: The webhook handler was not updating the next billing date after successful recurring charges.
resource: git:8f21c9a
tags: [backstory, ai-session]
timestamp: 2026-07-06T12:00:00+00:00
session_id: sha256:a1b2c3d4e5f6...
agent: claude-code
model: claude-sonnet-5
source: manual
branch: main
head: 8f21c9a...
commit_hash: 8f21c9a...
commit_message: Fix subscription renewal handling
files_changed:
  - app/api/webhooks/razorpay/route.ts
  - lib/subscription.ts
---

# Task

Fix subscription renewal handling

# Decisions

- subscription.charged updates next_due_on
- payment.failed marks subscription as pending, not cancelled
- webhook handling must be idempotent

# Risks

- Idempotency depends on storing Razorpay event IDs
- Existing subscriptions need a next_due_on backfill

# Follow-ups

- Add migration script for existing subscriptions
```

This file lives at `.backstory/knowledge/sessions/sha256-a1b2c3d4....md`.
It is human-readable, Git-friendly, and stores only the durable
decisions — not the full chat transcript.

## How It Works

![Backstory flow diagram](docs/assets/how-it-works-flow.gif)

![Backstory terminal walkthrough](docs/assets/how-it-works-terminal.gif)

The capture and retrieval pipeline has four steps:

1. **Capture** — A tool-native hook, callback, or transcript exporter
   captures the AI coding session and hands it to Backstory.
2. **Ingest** — Backstory extracts the durable decisions, risks, follow-ups,
   and changed files from the session. The raw conversation is discarded —
   only the reasoning is kept.
3. **Link** — The extracted session is attached to the relevant Git commit
   via `backstory attach HEAD`, creating a stable record in
   `.backstory/knowledge/sessions/`.
4. **Retrieve** — Later, you can query the stored reasoning by commit, file,
   line, range, or diff using commands like `backstory why HEAD`.

Git stays the linkage layer. Backstory stores the reasoning.

## Prerequisites

- **Python 3.11+** — Backstory requires Python 3.11 or newer.
- **pip or pipx** — Either package manager works. On fresh machines, `pipx` is
  recommended because it installs Backstory in its own isolated environment
  without needing a separate virtual environment.
- **Git** — Backstory stores session memory inside a Git repository and links
  it to commits.

## Install

Install directly from the repository:

```bash
# Using pip (system-wide or in a virtual environment)
python3 -m pip install git+https://github.com/arpitkath/backstory.git

# Using pipx (isolated, recommended for fresh machines)
pipx install git+https://github.com/arpitkath/backstory.git
```

Or install the PyPI package:

```bash
python -m pip install backstory-cli
```

The installed command is:

```bash
backstory --help
```

## First Run

Initialize Backstory in your repository:

```bash
backstory init
```

This creates a `.backstory/` directory in your repo with the necessary
storage, indexing, and configuration. It also optionally installs Git hooks
that help keep session memory linked to your commits.

## Verify

Check that everything is set up correctly:

```bash
backstory status
```

If you have an existing commit with a linked session, view its reasoning:

```bash
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
| `backstory hooks <enable\|disable\|status>` | Manage Git hook installation |

## Redaction

Backstory automatically scans for and redacts sensitive data before it reaches
disk. Here is what a session looks like when a transcript contains an API key:

```text
Before redaction:
  decisions:
    - "Store the key in RAZORPAY_API_KEY=sk_live_abcd1234..."
    - "Webhook endpoint is at https://api.example.com/webhooks"

After redaction:
  decisions:
    - "Store the key in RAZORPAY_API_KEY=***"
    - "Webhook endpoint is at https://api.example.com/webhooks"
```

The redaction step runs during `backstory dump` and can be re-run later with
`backstory redact` if new patterns are added. Raw transcripts are never
stored as the durable session record — only the redacted, extracted reasoning
persists.

## Storage

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
  Git context — not raw conversation

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

---

If you find this useful, [starring the repo](https://github.com/arpitkath/backstory)
helps others discover it.
