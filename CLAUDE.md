# CLAUDE.md

Repository instructions for Claude-based work in this repo.

## Project Summary

Backstory is a local-first AI memory layer for Git repositories. It stores
session history as OKF markdown under `.backstory/knowledge/` and links that
memory to commits. Capture should come from tool-native hooks, callbacks, or
transcript exporters, not from Git hooks.

## Current State

- Session persistence uses OKF markdown, not JSON.
- Pending sessions live at `.backstory/knowledge/sessions/latest.md`.
- Attached sessions live as stable `.md` files in the same directory.
- `backstory diff` can warn about likely contradictions with previous sessions.
- `backstory dump` is the ingestion step used by tool integrations.

## Important Commands

Use the local venv for verification:

```bash
PYTHONPATH=src /tmp/backstory-venv/bin/python -m pytest -q
```

Useful CLI commands:

```bash
backstory init
backstory attach HEAD
backstory why HEAD
backstory file <path>
backstory line <path>:<line>
backstory range <path>:<start>-<end>
backstory code <path>:<start>-<end>
backstory diff
backstory status
```

## Editing Rules

- Prefer small, scoped changes.
- Keep OKF as the persisted session format.
- Do not reintroduce durable JSON session storage.
- Prefer tool-native capture paths over Git hooks.
- Update tests when storage, parsing, or retrieval behavior changes.
- Treat the codebase as the source of truth when docs and implementation differ.

## Key Files

- `src/backstory/cli.py`
- `src/backstory/dump.py`
- `src/backstory/attach.py`
- `src/backstory/storage.py`
- `src/backstory/okf.py`
- `src/backstory/contradiction.py`
- `docs/prd.md`
- `docs/retrieval.md`
- `docs/engineering-walkthrough.md`

## Notes For Future Work

- Transcript ingestion is file-based and should be driven by the tool when
  possible.
- Retrieval is code-aware and Git-backed.
- Privacy and redaction are local-first concerns.
- If you change command behavior, update the docs in the same change.
