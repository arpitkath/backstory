from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

NOTE_REF = "refs/notes/backstory"


def _run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the CompletedProcess."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def read_git_note(repo_root: Path, commit_hash: str) -> dict[str, Any] | None:
    """Read the backstory Git note attached to a commit.

    Uses: git notes --ref={NOTE_REF} show {commit_hash}

    If no note exists, returns None.
    If note exists but isn't valid JSON, returns {"raw": content}.

    The note format is JSON:
    {
        "ai_session": "sha256:abc123",
        "agent": "claude-code",
        "created_at": "2026-07-05T12:00:00Z"
    }
    """
    try:
        result = _run_git(
            ["notes", f"--ref={NOTE_REF}", "show", commit_hash],
            cwd=repo_root,
            check=False,
        )
        if result.returncode != 0:
            return None
        content = result.stdout.strip()
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}
    except OSError:
        return None


def write_git_note(repo_root: Path, commit_hash: str, session: dict[str, Any]) -> bool:
    """Write a backstory Git note to a commit.

    Note content:
        "ai_session": session["session_id"],
        "agent": session.get("agent", {}).get("name", "unknown"),
        "created_at": session.get("created_at", ""),

    Uses: git notes --ref={NOTE_REF} add -f -m "{json}" {commit_hash}
    Returns True on success, False on failure.

    This is similar to the existing _write_git_note in attach.py.
    """
    try:
        note = json.dumps(
            {
                "ai_session": session["session_id"],
                "agent": session.get("agent", {}).get("name", "unknown"),
                "created_at": session.get("created_at", ""),
            }
        )
    except (KeyError, TypeError):
        return False

    try:
        result = _run_git(
            ["notes", f"--ref={NOTE_REF}", "add", "-f", "-m", note, commit_hash],
            cwd=repo_root,
            check=False,
        )
        return result.returncode == 0
    except OSError:
        return False


def remove_git_note(repo_root: Path, commit_hash: str) -> bool:
    """Remove a backstory Git note from a commit.

    Uses: git notes --ref={NOTE_REF} remove {commit_hash}
    Returns True if removed, False if no note existed or removal failed.
    """
    try:
        result = _run_git(
            ["notes", f"--ref={NOTE_REF}", "remove", commit_hash],
            cwd=repo_root,
            check=False,
        )
        return result.returncode == 0
    except OSError:
        return False


def list_noted_commits(repo_root: Path) -> list[tuple[str, dict[str, Any]]]:
    """List all commits with backstory notes attached.

    Uses: git notes list --ref={NOTE_REF}

    Returns list of (commit_hash, note_dict) tuples.
    Returns empty list if no notes or on failure.
    """
    try:
        result = _run_git(
            ["notes", f"--ref={NOTE_REF}", "list"],
            cwd=repo_root,
            check=False,
        )
        if result.returncode != 0:
            return []

        lines = result.stdout.strip().split("\n")
        results: list[tuple[str, dict[str, Any]]] = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.strip().split(None, 1)
            if not parts:
                continue
            # git notes list outputs: <note_object_sha> <commit_sha>
            commit_hash = parts[-1]
            note = read_git_note(repo_root, commit_hash)
            if note is not None:
                results.append((commit_hash, note))

        return results
    except OSError:
        return []


def migrate_notes_to_ref(repo_root: Path, commit_hash: str | None = None) -> bool:
    """Migrate a note (or all notes) to use the backstory-specific ref.

    Reads notes from the default ref (refs/notes/commits) and copies them
    to the backstory-specific ref (refs/notes/backstory).

    If commit_hash is given, migrate just that commit's note.
    If None, migrate all notes that contain "ai_session" in their content.

    Uses: git notes --ref={NOTE_REF} add -f -m "{content}" {commit_hash}
    Returns True if any note was migrated.
    """
    try:
        # List notes from the default ref (refs/notes/commits)
        result = _run_git(
            ["notes", "list"],
            cwd=repo_root,
            check=False,
        )
        if result.returncode != 0:
            return False

        lines = result.stdout.strip().split("\n")
        migrated = False

        for line in lines:
            if not line.strip():
                continue
            parts = line.strip().split(None, 1)
            if not parts:
                continue
            # git notes list outputs: <note_object_sha> <commit_sha>
            ch = parts[-1]

            if commit_hash is not None and ch != commit_hash:
                continue

            # Read note content from the default ref
            note_result = _run_git(
                ["notes", "show", ch],
                cwd=repo_root,
                check=False,
            )
            if note_result.returncode != 0:
                continue

            content = note_result.stdout.strip()
            if not content:
                continue

            # When migrating all, only copy notes that look like backstory notes
            if commit_hash is None and "ai_session" not in content:
                continue

            # Copy to the backstory ref
            write_result = _run_git(
                ["notes", f"--ref={NOTE_REF}", "add", "-f", "-m", content, ch],
                cwd=repo_root,
                check=False,
            )
            if write_result.returncode == 0:
                migrated = True

        return migrated
    except OSError:
        return False
