# OKF Session Storage Design

## Goal

Backstory will store factual AI session knowledge using Google's Open Knowledge Format (OKF) as the only source of truth. Durable session JSON files will be removed. The implementation does not need backward compatibility with existing `.backstory/pending/latest.json` or `.backstory/objects/*.json` files.

OKF means a directory of markdown concept documents with YAML frontmatter. Every concept must include `type`; Backstory will also use OKF's conventional `title`, `description`, `resource`, `tags`, and `timestamp` fields where they apply.

## Storage Layout

The canonical knowledge bundle will live under `.backstory/knowledge/`:

```text
.backstory/
  config.json
  knowledge/
    index.md
    sessions/
      index.md
      latest.md
      sha256-abc123.md
```

`latest.md` is the pending session concept. When a session is attached to a commit, the same concept is updated with commit metadata and moved to its stable session-id filename, such as `sha256-abc123.md`. After attach, `latest.md` no longer exists for that session. There is no persisted JSON mirror.

The `objects/`, `summaries/`, and `pending/latest.json` session paths should no longer be used for factual session data.

## Session Concept Format

Each AI session is one OKF concept file:

```md
---
type: Backstory Session
title: Fix subscription renewal handling
description: The webhook handler was not updating the next billing date after recurring charges.
resource: git:8f21c9a
tags: [backstory, ai-session, claude-code]
timestamp: 2026-07-06T10:30:00Z
session_id: sha256:abc123
agent: claude-code
model: claude-sonnet
source: hook
branch: main
head: a1b2c3
commit: 8f21c9a
files:
  - src/billing/webhook.py
---

# Task

Fix subscription renewal handling.

# Decisions

- subscription.charged updates next_due_on
- payment.failed marks subscription as pending, not cancelled

# Risks

- Existing users without next_due_on need backfill

# Follow-ups

- Add monitoring for webhook failures

# Alternatives

- Leave renewal date calculation to a scheduled reconciliation job

# Diff

## Staged

```diff
...
```

## Unstaged

```diff
...
```
```

Backstory-specific fields live in YAML frontmatter when they are useful for filtering or lookup. Longer factual content lives in markdown sections so humans and agents can read it directly.

## Runtime Model

Replace nested session dictionaries with an OKF-native model, tentatively named `SessionKnowledge`.

Responsibilities:

- Hold session metadata, decisions, risks, follow-ups, alternatives, affected files, and diffs.
- Render itself to an OKF markdown document.
- Parse an OKF markdown document back into a `SessionKnowledge` instance.
- Compute stable file-safe names from session IDs, for example `sha256:abc123` to `sha256-abc123.md`.

Public session operations should use this model instead of returning or accepting raw dictionaries.

## Command Behavior

`backstory dump` captures Git state and extracted factual decisions, then writes `.backstory/knowledge/sessions/latest.md`.

`backstory attach` loads `latest.md`, adds commit metadata, writes the stable session concept file, and removes or replaces `latest.md` so there is no second durable copy of the same pending facts.

`backstory why`, retrieval commands, and summary rendering read OKF concepts instead of JSON objects.

`backstory init` creates the OKF bundle directories and index files.

## Parsing And Formatting

The implementation should include a small YAML frontmatter parser and renderer. If project dependencies stay minimal, the parser can support the subset needed by Backstory:

- Frontmatter delimited by `---`.
- String scalar fields.
- Inline string arrays such as `tags: [backstory, ai-session]`.
- Block string arrays such as `files:`.

Markdown body sections should be parsed by heading names: `Task`, `Decisions`, `Risks`, `Follow-ups`, `Alternatives`, and `Diff`.

## Error Handling

If a concept file is missing, malformed, or lacks `type: Backstory Session`, commands should fail with a clear message and avoid writing partial replacement files.

If optional sections are missing, commands should treat them as empty factual lists.

If a session ID cannot be parsed into a safe filename, commands should reject it rather than guessing.

## Testing

Tests should cover:

- Storage initialization creates `.backstory/knowledge/index.md` and `.backstory/knowledge/sessions/index.md`.
- Dump writes `latest.md` and does not write `latest.json`.
- Captured sessions round-trip through OKF markdown.
- Attach writes a stable `sha256-*.md` session concept with commit metadata.
- Load failures for malformed OKF are explicit.
- No tests depend on persisted session JSON.

## Out Of Scope

This design does not include migration from existing JSON session files.

This design does not add a full OKF validator beyond the fields Backstory needs.

This design does not introduce a separate knowledge graph database or external indexing service.
