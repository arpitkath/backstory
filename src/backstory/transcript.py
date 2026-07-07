from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExtractedDecisions:
    """Factual information extracted from a transcript — no raw messages stored."""
    agent_name: str
    model: str | None
    task: str
    decisions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Transcript import (read + normalize only, no extraction)
# ---------------------------------------------------------------------------


def import_transcript(path: Path | str) -> dict[str, Any] | None:
    """Read a transcript file and return the raw parsed JSON.

    Supports both standard JSON and JSONL (one JSON object per line,
    as produced by Claude Code v2.1+). For JSONL files, user and
    assistant messages are extracted from ``type``/``message`` fields
    and merged into a ``messages`` array along with any top-level
    metadata.

    Returns ``None`` if the file cannot be read or parsed.
    The caller is responsible for passing the content to the
    agent summarizer (``summarize_transcript``).
    """
    if isinstance(path, str):
        path = Path(path)

    if not path.exists():
        return None

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None

    # Try standard JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # JSONL fallback — one JSON object per line (Claude Code v2.1+)
    try:
        return _import_jsonl(text)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def _import_jsonl(text: str) -> dict[str, Any] | None:
    """Parse a JSONL transcript into a merged dict with a ``messages`` array."""
    merged: dict[str, Any] = {}
    messages: list[dict[str, Any]] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        obj = json.loads(stripped)

        # Collect top-level metadata (agent, model, mode, etc.)
        if "type" not in obj:
            # Treat as a metadata-only line
            merged.update(obj)
            continue

        line_type = obj.get("type")

        # Session metadata
        if line_type in ("mode", "metadata", "info"):
            merged.update(obj)
            continue

        # User or assistant message
        if line_type in ("user", "assistant"):
            msg = obj.get("message")
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append(msg)
            continue

        # Treat any other typed line as metadata
        merged.update(obj)

    if not messages and not merged:
        return None

    merged["messages"] = messages

    # Detect agent from mode line metadata
    mode = merged.get("mode", "")
    if mode:
        merged.setdefault("agent", {})
        agent_block = merged["agent"]
        if isinstance(agent_block, dict) and not agent_block.get("name"):
            agent_block["name"] = "claude-code" if "claude" in str(mode).lower() else mode

    return merged


def normalize_messages(raw: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize any supported transcript format to ``[{role, content}, ...]``.

    Supports Claude Code (``messages`` / ``conversation`` arrays),
    Codex/OpenAI (``choices`` array with ``message`` objects),
    and generic (``dialog``, ``history``, ``chats``).
    """
    messages: list[dict[str, Any]] = []

    # Claude Code format
    if "messages" in raw and isinstance(raw["messages"], list):
        messages = raw["messages"]
    elif "conversation" in raw and isinstance(raw["conversation"], list):
        messages = raw["conversation"]

    # Codex / OpenAI format
    if not messages and "choices" in raw and isinstance(raw["choices"], list):
        for choice in raw["choices"]:
            if "message" in choice:
                messages.append(choice["message"])
            elif "delta" in choice:
                messages.append(choice["delta"])

    # Generic fallback
    if not messages:
        for key in ("dialog", "history", "chats"):
            if key in raw and isinstance(raw[key], list):
                messages = raw[key]
                break

    # Normalize to {role, content} strings
    result: list[dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, str):
            result.append({"role": "user", "content": msg})
        elif isinstance(msg, dict):
            role = str(msg.get("role", "user"))
            content = msg.get("content", "")
            if content is None:
                content = ""
            if isinstance(content, list):
                content = "\n".join(
                    p.get("text", json.dumps(p)) if isinstance(p, dict) else str(p)
                    for p in content
                )
            result.append({"role": role, "content": str(content)})

    return result


def detect_agent_name(raw: dict[str, Any]) -> str:
    """Detect the agent name from transcript metadata."""
    agent = raw.get("agent")
    if isinstance(agent, dict):
        name = agent.get("name") or agent.get("agent") or ""
        if name:
            return str(name)

    model = str(raw.get("model", ""))
    if "claude" in model.lower():
        return "claude-code"
    if "gpt" in model.lower() or "o1" in model.lower() or "o3" in model.lower():
        return "codex"
    if "deepseek" in model.lower() or "sonnet" in model.lower():
        return "claude-code"

    return "unknown"


def detect_model(raw: dict[str, Any]) -> str | None:
    """Extract model name from transcript metadata."""
    model = raw.get("model")
    if model:
        return str(model)
    agent = raw.get("agent")
    if isinstance(agent, dict) and "model" in agent:
        return str(agent["model"])
    return None


# ---------------------------------------------------------------------------
# Decision formatting for CLI output
# ---------------------------------------------------------------------------


def format_decisions(d: ExtractedDecisions) -> str:
    """Format extracted decisions for human-readable CLI output."""
    lines: list[str] = []

    lines.append(f"Agent: {d.agent_name or 'unknown'}")
    if d.model:
        lines.append(f"Model: {d.model}")
    lines.append("")

    if d.task:
        lines.append(f"Task: {d.task}")
        lines.append("")

    if d.decisions:
        lines.append("Decisions:")
        for dec in d.decisions[:20]:
            lines.append(f"  - {dec}")
        if len(d.decisions) > 20:
            lines.append(f"  ... and {len(d.decisions) - 20} more")
        lines.append("")

    if d.files_changed:
        lines.append("Files affected:")
        for f in d.files_changed[:15]:
            lines.append(f"  - {f}")
        if len(d.files_changed) > 15:
            lines.append(f"  ... and {len(d.files_changed) - 15} more")
        lines.append("")

    if d.risks:
        lines.append("Risks / Cautions:")
        for r in d.risks[:10]:
            lines.append(f"  - {r}")
        lines.append("")

    if d.followups:
        lines.append("Follow-ups:")
        for f in d.followups[:10]:
            lines.append(f"  - {f}")
        lines.append("")

    if d.alternatives:
        lines.append("Alternatives considered:")
        for a in d.alternatives[:5]:
            lines.append(f"  - {a}")

    return "\n".join(lines)
