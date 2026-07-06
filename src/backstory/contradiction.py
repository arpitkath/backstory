from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backstory.okf import parse_session_markdown
from backstory.storage import build_storage_paths

NEGATION_PATTERNS = (
    r"\bnot\b",
    r"\bnever\b",
    r"\binstead\b",
    r"\bavoid\b",
    r"\bprevent\b",
    r"\bno longer\b",
    r"\brather than\b",
)


def detect_potential_contradictions(repo_root: Path, changed_files: list[str]) -> list[str]:
    """Return human-readable warnings for likely contradictions.

    The first implementation is conservative: it only warns when a current
    changed file overlaps with a previously attached session and that session
    contains at least one negated or reversing decision.
    """
    changed = {path for path in changed_files if path}
    if not changed:
        return []

    warnings: list[str] = []
    for session in _load_attached_sessions(repo_root):
        session_files = set(session.get("files", {}).get("changed", []))
        overlap = sorted(changed.intersection(session_files))
        if not overlap:
            continue

        reasoning = session.get("reasoning_summary", {})
        decisions = reasoning.get("decisions", [])
        for decision in decisions:
            if _looks_like_reversal(decision):
                commit_hash = session.get("commit", {}).get("hash") or session.get("session_id", "unknown")
                warnings.append(
                    f"Potential contradiction from {str(commit_hash)[:7]} on {', '.join(overlap)}: {decision}"
                )
                break

    return warnings


def _load_attached_sessions(repo_root: Path) -> list[dict[str, Any]]:
    """Load attached session objects from local storage."""
    paths = build_storage_paths(repo_root)
    sessions: list[dict[str, Any]] = []

    if not paths.sessions.exists():
        return sessions

    for path in sorted(paths.sessions.glob("*.md")):
        if path.name == "latest.md":
            continue
        try:
            knowledge = parse_session_markdown(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        sessions.append(knowledge.to_session_dict())

    return sessions


def _looks_like_reversal(text: str) -> bool:
    """Detect the negated phrasing typically used in a contradictory decision."""
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in NEGATION_PATTERNS)
