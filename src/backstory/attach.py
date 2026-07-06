from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from backstory.dump import clear_pending_session, load_pending_session
from backstory.storage import build_storage_paths, ensure_storage_layout


def attach_pending_to_commit(repo_root: Path, commit_hash: str) -> dict[str, Any] | None:
    """Attach the latest pending AI session to a Git commit.

    Steps:
        1. Load the pending session.
        2. Update it with the commit hash.
        3. Write a summary file.
        4. Save commit-to-session mapping via Git notes.
        5. Clear the pending session.

    Returns the updated session dict, or ``None`` if no pending session exists.
    """
    session = load_pending_session(repo_root)
    if session is None:
        return None

    # --- Link session to commit ---
    commit_msg = _get_commit_message(repo_root, commit_hash)
    session["commit"] = {
        "hash": commit_hash,
        "message": commit_msg or "",
    }

    # --- Write a summary file ---
    paths = ensure_storage_layout(repo_root)
    summary_path = paths.summaries / f"{commit_hash}.md"
    summary_content = _render_summary(session, commit_hash, commit_msg)
    summary_path.write_text(summary_content, encoding="utf-8")

    # --- Save the session object ---
    object_path = paths.objects / f"{session['session_id']}.json"
    object_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")

    # --- Write a Git note ---
    _write_git_note(repo_root, commit_hash, session)

    # --- Clear pending ---
    clear_pending_session(repo_root)

    return session


def _get_commit_message(repo_root: Path, commit_hash: str) -> str | None:
    """Get the subject line of a commit."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", commit_hash],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
        return None
    except OSError:
        return None


def _write_git_note(repo_root: Path, commit_hash: str, session: dict) -> None:
    """Attach a Git note with session metadata to the commit."""
    note = json.dumps(
        {
            "ai_session": session.get("session_id"),
            "agent": session.get("agent", {}).get("name"),
            "created_at": session.get("created_at"),
        },
        indent=2,
    )
    try:
        subprocess.run(
            ["git", "notes", "add", "-f", "-m", note, commit_hash],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        pass  # Git notes are best-effort


def _render_summary(session: dict, commit_hash: str, commit_msg: str | None) -> str:
    """Render a human-readable summary markdown file."""
    agent = session.get("agent", {})
    task = session.get("task", {})
    files = session.get("files", {})
    reasoning = session.get("reasoning_summary", {})

    lines: list[str] = []
    lines.append(f"# backstory for Commit {commit_hash}")
    lines.append("")

    if commit_msg:
        lines.append(f"**{commit_msg}**")
        lines.append("")

    if task.get("title"):
        lines.append("## Task")
        lines.append("")
        lines.append(task["title"])
        lines.append("")

    if reasoning.get("why"):
        lines.append("## Why")
        lines.append("")
        lines.append(reasoning["why"])
        lines.append("")

    changed = files.get("changed", [])
    if changed:
        lines.append("## Files Changed")
        lines.append("")
        for f in changed:
            lines.append(f"- `{f}`")
        lines.append("")

    decisions = reasoning.get("decisions", [])
    if decisions:
        lines.append("## Key Decisions")
        lines.append("")
        for d in decisions:
            lines.append(f"- {d}")
        lines.append("")

    risks = reasoning.get("risks", [])
    if risks:
        lines.append("## Risks")
        lines.append("")
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    if agent.get("name"):
        lines.append(f"Agent: {agent['name']}")
    if agent.get("model"):
        lines.append(f"Model: {agent['model']}")
    lines.append("")

    lines.append(f"Session ID: {session.get('session_id', 'unknown')}")

    return "\n".join(lines)
