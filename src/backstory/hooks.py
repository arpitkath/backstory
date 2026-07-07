from __future__ import annotations

import os
import stat
from pathlib import Path


PRE_COMMIT_CONTENT = r"""#!/bin/sh
# backstory pre-commit hook — captures AI session context before committing
BACKSTORY="$(which backstory 2>/dev/null || echo backstory)"
if command -v "$BACKSTORY" >/dev/null 2>&1; then
    "$BACKSTORY" dump --hook pre-commit 2>/dev/null || true
fi
"""

POST_COMMIT_CONTENT = r"""#!/bin/sh
# backstory post-commit hook — attaches AI session to the new commit
BACKSTORY="$(which backstory 2>/dev/null || echo backstory)"
if command -v "$BACKSTORY" >/dev/null 2>&1; then
    "$BACKSTORY" attach HEAD --hook post-commit 2>/dev/null || true
fi
"""


def hooks_dir(repo_root: Path) -> Path:
    """Return the standard Git hooks directory for the repository."""
    return repo_root / ".git" / "hooks"


def install_hooks(repo_root: Path) -> list[Path]:
    """Install backstory Git hooks in the repository.

    Writes executable pre-commit and post-commit hook scripts
    that call backstory. Existing hooks are preserved; backstory's
    own hooks are overwritten on re-init.

    Returns a list of paths that were written.
    """
    target = hooks_dir(repo_root)
    target.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    for name, content in [("pre-commit", PRE_COMMIT_CONTENT), ("post-commit", POST_COMMIT_CONTENT)]:
        path = target / name
        path.write_text(content, encoding="utf-8")
        _make_executable(path)
        written.append(path)

    return written


def uninstall_hooks(repo_root: Path) -> int:
    """Remove backstory Git hooks from the repository.

    Only removes hook files that contain a backstory marker comment.
    Returns the number of hooks removed.
    """
    target = hooks_dir(repo_root)
    removed = 0

    for name in ("pre-commit", "post-commit"):
        path = target / name
        if path.exists() and _is_backstory_hook(path):
            path.unlink()
            removed += 1

    return removed


def hooks_installed(repo_root: Path) -> dict[str, bool]:
    """Return a dict mapping hook name to whether it's installed."""
    target = hooks_dir(repo_root)
    return {
        "pre-commit": _is_backstory_hook(target / "pre-commit"),
        "post-commit": _is_backstory_hook(target / "post-commit"),
    }


def _make_executable(path: Path) -> None:
    """Make a file executable (chmod +x)."""
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _is_backstory_hook(path: Path) -> bool:
    """Check if a hook file exists and contains the backstory marker."""
    if not path.exists():
        return False
    try:
        first_line = path.read_text(encoding="utf-8").strip()
        return "backstory" in first_line.lower()
    except Exception:
        return False
