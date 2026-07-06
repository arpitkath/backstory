from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backstory.storage import build_storage_paths, ensure_storage_layout


@dataclass
class SecretFinding:
    pattern_name: str  # e.g. "API Key", "Private Key", "Database URL"
    value_snippet: str  # First 20 chars of the finding (safe to display)
    context: str  # The field/line in the session where it was found
    confidence: float  # 0.0 to 1.0


SECRET_PATTERNS: list[tuple[str, str, float]] = [
    # (name, regex_pattern, confidence)
    ("AWS Access Key", r"AKIA[0-9A-Z]{16}", 0.95),
    ("GitHub Token", r"gh[pousr]_[A-Za-z0-9_]{36,}", 0.9),
    ("GitHub Old Token", r"gh_[a-f0-9]{20,}", 0.7),
    ("Private Key", r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", 0.99),
    ("API Key (generic)", r"(?i)api[_-]?key[=:]\s*['\"]?[A-Za-z0-9_\-]{20,}", 0.6),
    ("Bearer Token", r"bearer\s+[A-Za-z0-9_\-\.]{20,}", 0.8),
    ("Database URL", r"(?:postgres|mysql|mongodb|redis)://[^\s]+", 0.85),
    ("Slack Token", r"xox[baprs]-[0-9a-zA-Z-]{10,}", 0.9),
    ("JWT Token", r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", 0.8),
    ("Password in URL", r"//[^:/\s]+:[^@/\s]+@", 0.7),
]


def scan_session(session: dict[str, Any]) -> list[SecretFinding]:
    """Scan a session dict for potential secrets.

    Check these fields:
    - task.title, task.user_prompt
    - reasoning_summary.why, reasoning_summary.decisions (each item)
    - reasoning_summary.risks, reasoning_summary.followups
    - diff.staged, diff.unstaged
    - files.changed (each path)

    Returns sorted list of findings (highest confidence first).
    """
    findings: list[SecretFinding] = []

    # --- task fields ---
    task = session.get("task", {})
    if isinstance(task, dict):
        if "title" in task:
            findings.extend(scan_text(str(task["title"]), "task.title"))
        if "user_prompt" in task:
            findings.extend(scan_text(str(task["user_prompt"]), "task.user_prompt"))

    # --- reasoning_summary fields ---
    reasoning = session.get("reasoning_summary", {})
    if isinstance(reasoning, dict):
        for key in ("why",):
            value = reasoning.get(key)
            if value:
                findings.extend(scan_text(str(value), f"reasoning_summary.{key}"))

        for key in ("decisions", "risks", "followups", "alternatives"):
            items = reasoning.get(key)
            if isinstance(items, list):
                for i, item in enumerate(items):
                    findings.extend(scan_text(str(item), f"reasoning_summary.{key}[{i}]"))

    # --- diff fields ---
    diff = session.get("diff", {})
    if isinstance(diff, dict):
        if "staged" in diff:
            findings.extend(scan_text(str(diff["staged"]), "diff.staged"))
        if "unstaged" in diff:
            findings.extend(scan_text(str(diff["unstaged"]), "diff.unstaged"))

    # --- files.changed ---
    files = session.get("files", {})
    if isinstance(files, dict):
        changed = files.get("changed", [])
        if isinstance(changed, list):
            for i, path in enumerate(changed):
                findings.extend(scan_text(str(path), f"files.changed[{i}]"))

    # Sort: highest confidence first
    findings.sort(key=lambda f: f.confidence, reverse=True)
    return findings


def scan_text(text: str, context_label: str) -> list[SecretFinding]:
    """Scan a single text string for secret patterns. Internal helper."""
    findings: list[SecretFinding] = []
    if not text:
        return findings

    for name, pattern, confidence in SECRET_PATTERNS:
        matches: list[str] = re.findall(pattern, text)
        for match in matches:
            snippet = match[:20]
            findings.append(
                SecretFinding(
                    pattern_name=name,
                    value_snippet=snippet,
                    context=context_label,
                    confidence=confidence,
                )
            )
    return findings


def redact_session(
    session: dict[str, Any],
) -> tuple[dict[str, Any], list[SecretFinding]]:
    """Create a redacted copy of a session.

    For each field that contains a secret:
    - Replace the matched string with [REDACTED:{pattern_name}]
    - Return the new session dict (don't mutate original)
    - Also return the list of SecretFinding objects

    Fields to scan and redact (same as scan_session):
    - task.title, task.user_prompt
    - reasoning_summary.*  (all string and list-of-strings fields)
    - diff.staged, diff.unstaged
    """
    # Collect findings first so we can apply all redactions at once
    findings = scan_session(session)
    if not findings:
        return _deep_copy(session), findings

    # Start with a deep copy and redact in place
    redacted = _deep_copy(session)

    # --- task fields ---
    task = redacted.get("task", {})
    if isinstance(task, dict):
        if "title" in task and isinstance(task["title"], str):
            task["title"] = _redact_text(task["title"], findings)
        if "user_prompt" in task and isinstance(task["user_prompt"], str):
            task["user_prompt"] = _redact_text(task["user_prompt"], findings)

    # --- reasoning_summary fields ---
    reasoning = redacted.get("reasoning_summary", {})
    if isinstance(reasoning, dict):
        if "why" in reasoning and isinstance(reasoning["why"], str):
            reasoning["why"] = _redact_text(reasoning["why"], findings)

        for key in ("decisions", "risks", "followups", "alternatives"):
            items = reasoning.get(key)
            if isinstance(items, list):
                reasoning[key] = [
                    _redact_text(str(item), findings) for item in items
                ]

    # --- diff fields ---
    diff = redacted.get("diff", {})
    if isinstance(diff, dict):
        if "staged" in diff and isinstance(diff["staged"], str):
            diff["staged"] = _redact_text(diff["staged"], findings)
        if "unstaged" in diff and isinstance(diff["unstaged"], str):
            diff["unstaged"] = _redact_text(diff["unstaged"], findings)

    return redacted, findings


def _redact_text(text: str, findings: list[SecretFinding]) -> str:
    """Redact all matched secrets in a text string. Internal helper.

    For each finding, replaces all non-overlapping occurrences of the
    matched secret pattern with a redaction marker.
    """
    result = text
    # De-duplicate by (pattern_name, regex) so we only process each pattern once
    seen: set[tuple[str, str]] = set()
    unique_patterns: list[tuple[str, str, float]] = []
    for finding in findings:
        # Re-derive the corresponding regex for this pattern_name
        for name, pattern, confidence in SECRET_PATTERNS:
            if name == finding.pattern_name:
                key = (name, pattern)
                if key not in seen:
                    seen.add(key)
                    unique_patterns.append((name, pattern, confidence))
                break

    # Sort by confidence descending so more specific patterns are applied first
    unique_patterns.sort(key=lambda x: x[2], reverse=True)

    for name, pattern, _confidence in unique_patterns:
        result = re.sub(pattern, f"[REDACTED:{name}]", result)

    return result


def _deep_copy(session: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of a session dict.

    Handles nested dicts, lists, and primitive values. Does not handle
    custom objects or circular references.
    """
    result: dict[str, Any] = {}
    for key, value in session.items():
        if isinstance(value, dict):
            result[key] = _deep_copy(value)
        elif isinstance(value, list):
            result[key] = _deep_copy_list(value)
        else:
            result[key] = value
    return result


def _deep_copy_list(items: list[Any]) -> list[Any]:
    """Deep copy a list, handling nested dicts and lists."""
    result: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            result.append(_deep_copy(item))
        elif isinstance(item, list):
            result.append(_deep_copy_list(item))
        else:
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Tombstone management
# ---------------------------------------------------------------------------


def append_tombstone(
    repo_root: Path, old_session_id: str, new_session_id: str
) -> None:
    """Append a tombstone entry to .backstory/redactions/tombstones.log.

    Format per line (JSON):
    {"old": "sha256:abc123", "new": "sha256:def456", "timestamp": "2026-07-06T...", "reason": "redacted"}
    """
    paths = ensure_storage_layout(repo_root)
    tombstone_path = paths.redactions / "tombstones.log"

    entry = {
        "old": old_session_id,
        "new": new_session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": "redacted",
    }

    try:
        with open(tombstone_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError:
        pass


def load_tombstones(repo_root: Path) -> list[dict]:
    """Load all tombstone entries from .backstory/redactions/tombstones.log.

    Returns empty list if file doesn't exist or can't be read.
    """
    paths = build_storage_paths(repo_root)
    tombstone_path = paths.redactions / "tombstones.log"

    if not tombstone_path.exists():
        return []

    entries: list[dict] = []
    try:
        text = tombstone_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []

    return entries
