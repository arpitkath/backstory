from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from backstory import git_notes
from backstory.dump import clear_pending_session, load_pending_session
from backstory.okf import parse_session_markdown, render_session_markdown, session_id_to_filename
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

    paths = ensure_storage_layout(repo_root)
    stable_path = paths.sessions / session_id_to_filename(session["session_id"])
    stable_path.write_text(render_session_markdown(session), encoding="utf-8")

    # --- Write a Git note ---
    git_notes.write_git_note(repo_root, commit_hash, session)

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


def _render_summary(session: dict, commit_hash: str, commit_msg: str | None) -> str:
    """Render a human-readable summary markdown file."""
    rendered = render_session_markdown(session)
    parsed = parse_session_markdown(rendered)
    lines: list[str] = []
    lines.append(f"# backstory for Commit {commit_hash}")
    lines.append("")
    if commit_msg:
        lines.append(f"**{commit_msg}**")
        lines.append("")
    lines.append("## Task")
    lines.append("")
    lines.append(parsed.task_title)
    lines.append("")
    if parsed.why:
        lines.append("## Why")
        lines.append("")
        lines.append(parsed.why)
        lines.append("")
    if parsed.files_changed:
        lines.append("## Files Changed")
        lines.append("")
        for f in parsed.files_changed:
            lines.append(f"- `{f}`")
        lines.append("")
    if parsed.decisions:
        lines.append("## Key Decisions")
        lines.append("")
        for d in parsed.decisions:
            lines.append(f"- {d}")
        lines.append("")
    if parsed.risks:
        lines.append("## Risks")
        lines.append("")
        for r in parsed.risks:
            lines.append(f"- {r}")
        lines.append("")
    lines.append(f"Agent: {parsed.agent_name}")
    if parsed.agent_model:
        lines.append(f"Model: {parsed.agent_model}")
    lines.append("")
    lines.append(f"Session ID: {parsed.session_id or session.get('session_id', 'unknown')}")
    return "\n".join(lines)
