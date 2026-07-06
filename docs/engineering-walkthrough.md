# Backstory Engineering Walkthrough

Backstory is a local-first Git-backed memory layer for AI-assisted coding. It
captures session context, stores the durable record as OKF markdown, attaches
that memory to commits, and later retrieves the reasoning behind code changes.

## What It Does

The tool helps answer questions like:

- Why did this commit happen?
- Why does this file or line exist?
- What prior AI context matters for this diff?

The current implementation is fully local. It does not depend on a service or
hosted backend.

## Storage Model

Backstory now uses OKF markdown as the persisted source of truth for session
memory.

Primary storage layout:

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

Key points:

- `latest.md` is the pending session file.
- Attached sessions are stable `.md` files under `knowledge/sessions/`.
- The repository still keeps config and local index metadata alongside the OKF
  bundle.

## Main Flow

### 1. Initialize

Run:

```bash
backstory init
```

This creates the storage layout and installs Git hooks.

### 2. Capture a session

Run manually:

```bash
backstory dump
```

Or point it at a transcript:

```bash
backstory dump --agent claude --transcript ./transcript.md
```

If no transcript is provided, the CLI can auto-discover one from environment
variables or common repo-local transcript paths.

### 3. Commit

The Git hooks handle the handoff:

- pre-commit captures the pending state
- post-commit attaches the session to the final commit hash

### 4. Retrieve context

The retrieval surface is code-aware:

```bash
backstory why HEAD
backstory file src/auth/session.ts
backstory line src/auth/session.ts:120
backstory range src/auth/session.ts:100-160
backstory code src/auth/session.ts:100-160
backstory diff
```

`backstory diff` also surfaces contradiction warnings when a new change appears
to reverse an earlier recorded decision.

## Integration With Claude, Codex, and Cursor

Backstory is file-based, not SDK-based.

Integration options:

- Export a transcript file and pass it to `backstory dump --transcript ...`
- Set one of the supported transcript path environment variables and let the
  CLI discover it
- Use the Git hooks so the session is attached automatically around commits

The tool does not require a special extension to be useful. It works with any
AI tool that can emit a local transcript or leave a diff in the repository.

## What The Commands Mean

- `init`: create local storage and hooks
- `dump`: capture the current AI session into OKF markdown
- `attach`: link a saved session to a commit
- `why`: explain a commit
- `show`: inspect a stored session
- `search`: find sessions by text and metadata
- `file`, `line`, `range`, `code`: explain code with history context
- `diff`: inspect uncommitted changes with prior context warnings
- `status`: inspect local memory state
- `redact`: re-run redaction on stored sessions

Some command names are already implemented, and some are still the intended
surface area from the docs. Treat the code as authoritative for exact behavior.

## Security And Privacy

Backstory is local by default.

- It stores session memory in the repository
- It redacts obvious secrets before persistence
- It does not upload data by default
- It keeps raw transcript handling out of the persisted session record

## How To Work On The Codebase

Important entry points:

- `src/backstory/cli.py`
- `src/backstory/dump.py`
- `src/backstory/attach.py`
- `src/backstory/storage.py`
- `src/backstory/okf.py`
- `src/backstory/contradiction.py`

Tests live under `tests/` and cover the storage layout, parsing, attachment,
transcript discovery, and contradiction warnings.

Verification command:

```bash
PYTHONPATH=src /tmp/backstory-venv/bin/python -m pytest -q
```

## Current Limitations

- Retrieval is still heuristic and Git-based.
- Contradiction detection is conservative rather than semantic.
- The CLI surface is ahead of some docs in a few places, so code should be
  treated as the source of truth.

