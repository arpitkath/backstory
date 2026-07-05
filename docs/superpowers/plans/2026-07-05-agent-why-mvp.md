# agent-why MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first Python CLI that captures AI coding sessions, stores them as compressed immutable objects, links them to Git commits, and explains `why` a commit happened.

**Architecture:** Use a small Python package with a single CLI entrypoint, a storage layer backed by `.agent-why/` plus SQLite, and focused helper modules for Git state, redaction, compression, and summary rendering. Keep command handlers thin and move repository logic into reusable functions so `init`, `dump`, `attach`, `why`, `show`, `status`, `search`, `context`, `redact`, and `repair` share the same storage and indexing primitives.

**Tech Stack:** Python 3.11+, `argparse`, `sqlite3`, `json`, `hashlib`, `subprocess`, `pathlib`, `zstandard`, `pytest`.

---

### Task 1: Scaffold the package and CLI router

**Files:**
- Create: `pyproject.toml`
- Create: `src/agent_why/__init__.py`
- Create: `src/agent_why/__main__.py`
- Create: `src/agent_why/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from agent_why.cli import build_parser


def test_cli_exposes_core_commands(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "init" in help_text
    assert "dump" in help_text
    assert "why" in help_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_cli_exposes_core_commands -v`
Expected: FAIL because `agent_why.cli.build_parser` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-why")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in [
        "init",
        "dump",
        "attach",
        "why",
        "show",
        "search",
        "context",
        "status",
        "redact",
        "repair",
    ]:
        subparsers.add_parser(name)
    return parser


def main() -> int:
    build_parser().parse_args()
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_cli_exposes_core_commands -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/agent_why tests/test_cli.py
git commit -m "feat: scaffold agent-why cli"
```

### Task 2: Add repository, config, and storage primitives

**Files:**
- Create: `src/agent_why/config.py`
- Create: `src/agent_why/storage.py`
- Create: `src/agent_why/git.py`
- Create: `tests/test_storage.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from agent_why.storage import repo_root, storage_paths


def test_storage_paths_are_under_agent_why(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()

    paths = storage_paths(root)

    assert paths.base == root / ".agent-why"
    assert paths.objects == root / ".agent-why" / "objects"
    assert paths.index_db == root / ".agent-why" / "index.sqlite"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py::test_storage_paths_are_under_agent_why -v`
Expected: FAIL because `storage_paths` is not implemented yet.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoragePaths:
    base: Path
    objects: Path
    summaries: Path
    pending: Path
    redactions: Path
    index_db: Path


def storage_paths(repo_root: Path) -> StoragePaths:
    base = repo_root / ".agent-why"
    return StoragePaths(
        base=base,
        objects=base / "objects",
        summaries=base / "summaries",
        pending=base / "pending",
        redactions=base / "redactions",
        index_db=base / "index.sqlite",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py::test_storage_paths_are_under_agent_why -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_why tests/test_storage.py tests/test_config.py
git commit -m "feat: add storage primitives"
```

### Task 3: Implement `agent-why init` and hook installation

**Files:**
- Modify: `src/agent_why/cli.py`
- Create: `src/agent_why/init.py`
- Create: `src/agent_why/hooks.py`
- Create: `tests/test_init.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from agent_why.init import initialize_repo


def test_init_creates_agent_why_layout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    initialize_repo(repo, install_hooks=True)

    assert (repo / ".agent-why").is_dir()
    assert (repo / ".agent-why" / "config.json").is_file()
    assert (repo / ".agent-why" / "objects").is_dir()
    assert (repo / ".git" / "hooks" / "pre-commit").exists()
    assert (repo / ".git" / "hooks" / "post-commit").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_init.py::test_init_creates_agent_why_layout -v`
Expected: FAIL because `initialize_repo` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
import json
from pathlib import Path

from .storage import storage_paths


DEFAULT_CONFIG = {
    "version": "1.0",
    "storage": {"mode": "local", "compress": True, "compression": "zstd"},
    "git": {"useGitNotes": True, "autoAttach": True},
    "hooks": {
        "preCommit": {"enabled": True, "captureStagedDiff": True, "blockOnSecrets": False},
        "postCommit": {"enabled": True, "autoAttach": True},
    },
    "redaction": {"enabled": True, "blockOnHighConfidenceSecrets": False, "customPatterns": []},
}


def initialize_repo(repo_root: Path, install_hooks: bool = True) -> None:
    paths = storage_paths(repo_root)
    paths.base.mkdir(parents=True, exist_ok=True)
    paths.objects.mkdir(parents=True, exist_ok=True)
    paths.summaries.mkdir(parents=True, exist_ok=True)
    paths.pending.mkdir(parents=True, exist_ok=True)
    paths.redactions.mkdir(parents=True, exist_ok=True)
    paths.index_db.touch(exist_ok=True)
    paths.base.joinpath("config.json").write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    if install_hooks:
        # hook installation stub for the first pass
        (repo_root / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nagent-why dump --hook pre-commit\n", encoding="utf-8")
        (repo_root / ".git" / "hooks" / "post-commit").write_text("#!/bin/sh\nagent-why attach HEAD --hook post-commit\n", encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_init.py::test_init_creates_agent_why_layout -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_why tests/test_init.py
git commit -m "feat: add agent-why init"
```

### Task 4: Implement `agent-why dump` with redaction, compression, and pending state

**Files:**
- Create: `src/agent_why/redact.py`
- Create: `src/agent_why/session.py`
- Create: `src/agent_why/dump.py`
- Modify: `src/agent_why/cli.py`
- Create: `tests/test_dump.py`
- Create: `tests/test_redact.py`

- [ ] **Step 1: Write the failing test**

```python
from agent_why.redact import redact_text


def test_redact_text_masks_obvious_secrets():
    text = "TOKEN=abcd1234\npassword=supersecret\nok=yes"
    redacted = redact_text(text)
    assert "[REDACTED]" in redacted
    assert "supersecret" not in redacted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_redact.py::test_redact_text_masks_obvious_secrets -v`
Expected: FAIL because `redact_text` is missing.

- [ ] **Step 3: Write minimal implementation**

```python
import re


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password)\s*=\s*[^\s]+"),
]


def redact_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: match.group(1).split("=")[0] + "=[REDACTED]", redacted)
    return redacted
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_redact.py::test_redact_text_masks_obvious_secrets -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_why tests/test_dump.py tests/test_redact.py
git commit -m "feat: add dump redaction and session storage"
```

### Task 5: Implement commit linking and retrieval commands

**Files:**
- Create: `src/agent_why/attach.py`
- Create: `src/agent_why/why.py`
- Create: `src/agent_why/show.py`
- Create: `src/agent_why/status.py`
- Create: `src/agent_why/summary.py`
- Modify: `src/agent_why/cli.py`
- Create: `tests/test_attach.py`
- Create: `tests/test_summary.py`
- Create: `tests/test_status.py`

- [ ] **Step 1: Write the failing test**

```python
from agent_why.summary import render_summary


def test_render_summary_includes_commit_and_task():
    summary = render_summary(
        commit_hash="8f21c9a",
        task="Fix subscription renewal handling",
        why="Webhook handling needed to update renewal state.",
        files_changed=["lib/subscription.py"],
    )
    assert "8f21c9a" in summary
    assert "Fix subscription renewal handling" in summary
    assert "lib/subscription.py" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_summary.py::test_render_summary_includes_commit_and_task -v`
Expected: FAIL because `render_summary` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def render_summary(commit_hash: str, task: str, why: str, files_changed: list[str]) -> str:
    files = "\n".join(f"- {path}" for path in files_changed)
    return (
        f"# agent-why for Commit {commit_hash}\n\n"
        f"## Task\n\n{task}\n\n"
        f"## Why\n\n{why}\n\n"
        f"## Files Changed\n\n{files}\n"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_why.py::test_render_summary_includes_commit_and_task -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_why tests/test_attach.py tests/test_summary.py tests/test_status.py
git commit -m "feat: add commit explanation commands"
```

### Task 6: Add search, context, redaction repair, and final polish

**Files:**
- Create: `src/agent_why/search.py`
- Create: `src/agent_why/context.py`
- Create: `src/agent_why/repair.py`
- Modify: `src/agent_why/cli.py`
- Create: `tests/test_search.py`
- Create: `tests/test_context.py`
- Create: `tests/test_repair.py`

- [ ] **Step 1: Write the failing test**

```python
from agent_why.search import normalize_query


def test_normalize_query_lowercases_and_trims():
    assert normalize_query("  Razorpay  ") == "razorpay"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search.py::test_normalize_query_lowercases_and_trims -v`
Expected: FAIL because `normalize_query` is not implemented.

- [ ] **Step 3: Write minimal implementation**

```python
def normalize_query(query: str) -> str:
    return query.strip().lower()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_search.py::test_normalize_query_lowercases_and_trims -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_why tests/test_search.py tests/test_context.py tests/test_repair.py
git commit -m "feat: add search and repair helpers"
```

### Coverage check

- `init`, storage layout, config, and hook installation are covered by Tasks 2 and 3.
- `dump`, redaction, and compressed session storage are covered by Task 4.
- `attach`, `why`, `show`, `status`, and summary rendering are covered by Task 5.
- `search`, `context`, and `repair` are covered by Task 6.
- The plan keeps the implementation local-first and Python-only, matching the updated PRD.
