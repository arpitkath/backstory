from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backstory.okf import (
    parse_session_markdown,
    render_session_markdown,
    session_id_to_filename,
)
from backstory.storage import build_storage_paths, ensure_storage_layout
from backstory.transcript import ExtractedDecisions

TRANSCRIPT_ENV_VARS = (
    "BACKSTORY_TRANSCRIPT",
    "CLAUDE_TRANSCRIPT_PATH",
    "CURSOR_TRANSCRIPT_PATH",
    "CODEX_TRANSCRIPT_PATH",
)


def capture_session(
    repo_root: Path,
    task: str | None = None,
    agent: str | None = None,
    decisions: ExtractedDecisions | None = None,
) -> dict[str, Any]:
    """Capture the current AI coding session as a structured dict.

    Stores Git state, agent metadata, task description, and the
    extracted factual decisions — no raw conversation content.

    Parameters
    ----------
    repo_root:
        Root of the Git repository.
    task:
        Optional short task description from the user.
    agent:
        Optional agent name override.
    decisions:
        Extracted decisions from a transcript (agent name, model,
        task, decisions, risks, follow-ups, files changed).
    """
    now = datetime.now(timezone.utc)

    # --- Git state ---
    branch = _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    head = _git_output(repo_root, "rev-parse", "HEAD")
    diff_staged = _git_output(repo_root, "diff", "--staged")
    diff_unstaged = _git_output(repo_root, "diff")
    changed_files_str = _git_output(repo_root, "diff", "--name-only")
    changed_files = [f for f in changed_files_str.split("\n") if f] if changed_files_str else []

    # --- Resolve agent info (decisions object takes priority) ---
    agent_name: str = "manual"
    agent_model: str | None = None
    if decisions:
        agent_name = decisions.agent_name or agent or "manual"
        agent_model = decisions.model
    elif agent:
        agent_name = agent

    # --- Build reasoning summary from extracted decisions ---
    if decisions:
        why = decisions.task or task or ""
        decisions_list = decisions.decisions[:]
        risks_list = decisions.risks[:]
        followups_list = decisions.followups[:]
        alternatives_list = decisions.alternatives[:]
        # Merge file references from transcript into git changed files
        if decisions.files_changed:
            changed_files = list(dict.fromkeys(decisions.files_changed + changed_files))
    else:
        why = task or ""
        decisions_list = []
        risks_list = []
        followups_list = []
        alternatives_list = []

    # --- Build session (NO raw conversation data) ---
    session_id = _compute_session_id(repo_root, now, task or "", decisions_list)

    session: dict[str, Any] = {
        "version": "1.0",
        "session_id": session_id,
        "created_at": now.isoformat(),
        "repo": {
            "branch": branch or "unknown",
            "head": head or "unknown",
        },
        "agent": {
            "name": agent_name,
            "model": agent_model,
            "source": "hook" if agent is None and not task else "manual",
        },
        "task": {
            "title": task or why,
            "user_prompt": task or "",
        },
        "files": {
            "changed": changed_files,
        },
        "diff": {
            "staged": diff_staged,
            "unstaged": diff_unstaged,
        },
        "reasoning_summary": {
            "why": why,
            "decisions": decisions_list,
            "risks": risks_list,
            "followups": followups_list,
            "alternatives": alternatives_list,
        },
        "commit": None,
    }

    return session


def discover_transcript_path(repo_root: Path) -> Path | None:
    """Discover a likely transcript file without requiring an explicit flag."""
    for env_var in TRANSCRIPT_ENV_VARS:
        raw_path = os.environ.get(env_var)
        if not raw_path:
            continue
        candidate = Path(raw_path).expanduser()
        if candidate.exists():
            return candidate

    for candidate in _repo_transcript_candidates(repo_root):
        if candidate.exists():
            return candidate

    return None


def save_pending_session(repo_root: Path, session: dict[str, Any]) -> Path:
    """Save a session dict as the latest pending session.

    Returns the path to the pending session file.
    """
    paths = ensure_storage_layout(repo_root)
    pending_path = paths.pending
    pending_path.write_text(render_session_markdown(session), encoding="utf-8")
    return pending_path


def load_pending_session(repo_root: Path) -> dict[str, Any] | None:
    """Load the latest pending session, or None."""
    paths = build_storage_paths(repo_root)
    pending_path = paths.pending
    if not pending_path.exists():
        return None
    try:
        knowledge = parse_session_markdown(pending_path.read_text(encoding="utf-8"))
        return knowledge.to_session_dict()
    except OSError:
        return None


def clear_pending_session(repo_root: Path) -> bool:
    """Remove the pending session file. Returns True if it existed."""
    paths = build_storage_paths(repo_root)
    pending_path = paths.pending
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
    task: str,
    decisions: list[str],
) -> str:
    """Compute a content-addressed session ID (SHA-256).

    Uses only factual data (task, decisions, git HEAD) — no raw
    conversation content.
    """
    hasher = hashlib.sha256()
    hasher.update(timestamp.isoformat().encode())
    hasher.update(task.encode())
    for d in decisions:
        hasher.update(d.encode())
    head = _git_output(repo_root, "rev-parse", "HEAD")
    if head:
        hasher.update(head.encode())
    return f"sha256:{hasher.hexdigest()[:32]}"


def _repo_transcript_candidates(repo_root: Path) -> list[Path]:
    """Return repo-local transcript locations ordered from most to least likely."""
    transcripts_dir = repo_root / ".backstory" / "transcripts"
    candidates = [
        transcripts_dir / "latest.json",
        transcripts_dir / "latest.jsonl",
        transcripts_dir / "session.json",
        repo_root / ".backstory" / "pending" / "transcript.json",
    ]

    if transcripts_dir.exists():
        for path in sorted(transcripts_dir.glob("*.json*")):
            if path not in candidates:
                candidates.append(path)

    return candidates
