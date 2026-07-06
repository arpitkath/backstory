from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backstory.storage import BackstoryPaths, build_storage_paths, ensure_storage_layout
from backstory.transcript import ParsedTranscript, import_transcript


def capture_session(
    repo_root: Path,
    task: str | None = None,
    agent: str | None = None,
    transcript: ParsedTranscript | None = None,
) -> dict[str, Any]:
    """Capture the current AI coding session as a structured dict.

    Gathers Git state, the optional task description, agent metadata,
    and transcript content into a session object ready for storage.
    """
    now = datetime.now(timezone.utc)

    # --- Git state ---
    branch = _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    head = _git_output(repo_root, "rev-parse", "HEAD")
    diff_staged = _git_output(repo_root, "diff", "--staged")
    diff_unstaged = _git_output(repo_root, "diff")
    changed_files_str = _git_output(repo_root, "diff", "--name-only")
    changed_files = [f for f in changed_files_str.split("\n") if f] if changed_files_str else []

    # --- Conversation ---
    conversation: list[dict[str, str]] = []
    if transcript:
        for msg in transcript.messages:
            conversation.append({"role": msg.role, "content": msg.content})

    # --- Build session ---
    # We need a content hash so the session is addressable.
    session_id = _compute_session_id(repo_root, now, conversation, task or "")

    session: dict[str, Any] = {
        "version": "1.0",
        "session_id": session_id,
        "created_at": now.isoformat(),
        "repo": {
            "branch": branch or "unknown",
            "head": head or "unknown",
        },
        "agent": {
            "name": transcript.agent_name if transcript else agent or "manual",
            "model": transcript.model if transcript else None,
            "source": "hook" if agent is None and not task else "manual",
        },
        "task": {
            "title": task or "",
            "user_prompt": task or "",
        },
        "conversation": conversation,
        "files": {
            "changed": changed_files,
        },
        "diff": {
            "staged": diff_staged,
            "unstaged": diff_unstaged,
        },
        "reasoning_summary": {
            "why": "",
            "decisions": [],
            "risks": [],
        },
        "commit": None,
    }

    return session


def save_pending_session(repo_root: Path, session: dict[str, Any]) -> Path:
    """Save a session dict as the latest pending session.

    Returns the path to the pending session file.
    """
    paths = ensure_storage_layout(repo_root)
    pending_path = paths.pending / "latest.json"
    pending_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    return pending_path


def load_pending_session(repo_root: Path) -> dict[str, Any] | None:
    """Load the latest pending session, or None."""
    paths = build_storage_paths(repo_root)
    pending_path = paths.pending / "latest.json"
    if not pending_path.exists():
        return None
    try:
        return json.loads(pending_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_pending_session(repo_root: Path) -> bool:
    """Remove the pending session file. Returns True if it existed."""
    paths = build_storage_paths(repo_root)
    pending_path = paths.pending / "latest.json"
    if pending_path.exists():
        pending_path.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _git_output(repo_root: Path, *args: str) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    except OSError:
        return ""


def _compute_session_id(
    repo_root: Path,
    timestamp: datetime,
    conversation: list[dict[str, str]],
    task: str,
) -> str:
    """Compute a content-addressed session ID (SHA-256)."""
    hasher = hashlib.sha256()
    hasher.update(timestamp.isoformat().encode())
    hasher.update(task.encode())
    if conversation:
        hasher.update(json.dumps(conversation, sort_keys=True).encode())
    head = _git_output(repo_root, "rev-parse", "HEAD")
    if head:
        hasher.update(head.encode())
    return f"sha256:{hasher.hexdigest()[:32]}"
