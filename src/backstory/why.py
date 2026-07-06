from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from backstory.okf import parse_session_markdown, session_id_to_filename
from backstory.storage import build_storage_paths


def _run_git(
    args: list[str], cwd: Path, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a git command and return the completed process."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def resolve_commit_spec(repo_root: Path, spec: str) -> tuple[str, str] | None:
    """Resolve a commit spec like 'HEAD', 'abc123', 'main~3' to (hash, message).

    Returns ``None`` if the commit doesn't exist.

    Uses ``git log -1 --format=%H%n%s <spec>``.
    """
    result = _run_git(
        ["log", "-1", "--format=%H%n%s", spec],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    lines = result.stdout.strip().split("\n", 1)
    commit_hash = lines[0].strip()
    commit_message = lines[1].strip() if len(lines) > 1 else ""
    return commit_hash, commit_message


def load_session_for_commit(
    repo_root: Path, commit_hash: str
) -> dict[str, Any] | None:
    """Load the AI session attached to a commit.

    Two strategies:

    1. **Git notes first** -- read the note attached to the commit via
       ``git notes show <commit>`` and use the stored session ID to
       locate the session file.

    2. **Fallback scan** -- list every ``.md`` file under
       ``.backstory/knowledge/sessions/``, parse its frontmatter, and
       return the first session whose ``commit_hash`` matches.

    Returns the session dict (the same structure that ``capture_session``
    in ``dump.py`` produces), or ``None`` if no session is found.
    """
    # ------------------------------------------------------------------
    # Strategy 1: Git notes
    # ------------------------------------------------------------------
    result = _run_git(
        ["notes", "--ref=refs/notes/backstory", "show", commit_hash],
        cwd=repo_root,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            note_data = json.loads(result.stdout)
            session_id = note_data.get("ai_session")
            if session_id:
                paths = build_storage_paths(repo_root)
                session_file = paths.sessions / session_id_to_filename(session_id)
                if session_file.exists():
                    knowledge = parse_session_markdown(
                        session_file.read_text(encoding="utf-8")
                    )
                    return knowledge.to_session_dict()
        except (json.JSONDecodeError, OSError):
            pass

    # ------------------------------------------------------------------
    # Strategy 2: Scan session files
    # ------------------------------------------------------------------
    paths = build_storage_paths(repo_root)
    if not paths.sessions.exists():
        return None

    for session_file in sorted(paths.sessions.glob("*.md")):
        if session_file.name == "latest.md":
            continue
        try:
            knowledge = parse_session_markdown(
                session_file.read_text(encoding="utf-8")
            )
            if knowledge.commit_hash == commit_hash:
                return knowledge.to_session_dict()
        except (OSError, ValueError):
            continue

    return None


def format_why_output(
    session: dict[str, Any], commit_hash: str, commit_message: str
) -> str:
    """Format a human-readable 'why' output string.

    Output format::

        Commit: <hash>
        Message: <message>
        Branch: <branch>
        AI Agent: <agent name>
        Session: <session_id>

        Task:
        <task title or why text>

        Key decisions:
        - <decision 1>
        - <decision 2>

        Files changed:
        - <file 1>
        - <file 2>

        Risks:
        - <risk 1>

        Follow-ups:
        - <followup 1>

        Raw session:
        .backstory/knowledge/sessions/<session_id_filename>
    """
    repo_info = session.get("repo", {})
    agent_info = session.get("agent", {})
    task_info = session.get("task", {})
    reasoning = session.get("reasoning_summary", {})
    files_info = session.get("files", {})
    session_id = session.get("session_id") or "unknown"

    lines: list[str] = []
    lines.append(f"Commit: {commit_hash}")
    lines.append(f"Message: {commit_message}")
    lines.append(f"Branch: {repo_info.get('branch') or 'unknown'}")
    lines.append(f"AI Agent: {agent_info.get('name') or 'unknown'}")
    lines.append(f"Session: {session_id}")
    lines.append("")

    # Task section
    task_title = task_info.get("title", "") or ""
    why_text = reasoning.get("why", "") or ""
    task_display = task_title or why_text or "(no task description)"
    lines.append("Task:")
    lines.append(f"{task_display}")
    lines.append("")

    # Key decisions
    decisions = reasoning.get("decisions", [])
    if decisions:
        lines.append("Key decisions:")
        for d in decisions:
            lines.append(f"  - {d}")
        lines.append("")

    # Files changed
    files_changed = files_info.get("changed", [])
    if files_changed:
        lines.append("Files changed:")
        for f in files_changed:
            lines.append(f"  - {f}")
        lines.append("")

    # Risks
    risks = reasoning.get("risks", [])
    if risks:
        lines.append("Risks:")
        for r in risks:
            lines.append(f"  - {r}")
        lines.append("")

    # Follow-ups
    followups = reasoning.get("followups", [])
    if followups:
        lines.append("Follow-ups:")
        for f in followups:
            lines.append(f"  - {f}")
        lines.append("")

    # Raw session path
    filename = session_id_to_filename(session_id)
    lines.append("Raw session:")
    lines.append(f".backstory/knowledge/sessions/{filename}")

    return "\n".join(lines)
