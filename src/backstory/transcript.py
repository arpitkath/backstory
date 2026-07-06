from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any


@dataclass
class ConversationEntry:
    role: str
    content: str


@dataclass
class ParsedTranscript:
    agent_name: str
    model: str | None
    messages: list[ConversationEntry]
    raw: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Claude Code transcript
# ---------------------------------------------------------------------------

CLAUDE_AGENT_NAMES = {"claude-code", "claude", "claude-code-cli"}


def _detect_claude_transcript(data: dict[str, Any]) -> bool:
    """Detect if a JSON dict is a Claude Code transcript.

    Claude Code transcripts typically have a ``"messages"`` key
    containing a list of ``{"role": ..., "content": ...}`` objects,
    or a ``"conversation"`` key.
    """
    if "messages" in data and isinstance(data["messages"], list):
        if data["messages"] and isinstance(data["messages"][0], dict):
            entry = data["messages"][0]
            if "role" in entry and "content" in entry:
                return True
    if "conversation" in data and isinstance(data["conversation"], list):
        return True
    return False


def _parse_claude_transcript(data: dict[str, Any]) -> ParsedTranscript:
    """Parse a Claude Code transcript dict into a structured result."""
    messages: list[dict] = data.get("messages") or data.get("conversation") or []

    model = data.get("model") or data.get("agent", {}).get("model")
    if not model and messages:
        # Try to extract model from metadata or first assistant message
        pass

    parsed_messages: list[ConversationEntry] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Some transcripts nest content under a "parts" array
        if isinstance(content, list):
            content = "\n".join(
                p.get("text", json.dumps(p)) if isinstance(p, dict) else str(p)
                for p in content
            )
        parsed_messages.append(ConversationEntry(role=role, content=str(content)))

    # Fallback model extraction from first assistant message if available
    if not model:
        for msg in messages:
            if msg.get("role") == "assistant" and isinstance(msg, dict):
                model = msg.get("model")
                if model:
                    break

    return ParsedTranscript(
        agent_name="claude-code",
        model=model or None,
        messages=parsed_messages,
        raw=data,
    )


# ---------------------------------------------------------------------------
# Codex / OpenAI-style transcript
# ---------------------------------------------------------------------------

CODEX_AGENT_NAMES = {"codex", "openai-codex", "codex-cli"}


def _detect_codex_transcript(data: dict[str, Any]) -> bool:
    """Detect if a JSON dict is a Codex / OpenAI-style transcript.

    Codex transcripts typically have a ``"choices"`` key or
    a ``"messages"`` key where entries contain ``"role"`` and ``"content"``.
    They may also use the OpenAI chat completions format.
    """
    if "choices" in data and isinstance(data["choices"], list):
        return True
    if "messages" in data and isinstance(data["messages"], list):
        if data["messages"] and isinstance(data["messages"][0], dict):
            entry = data["messages"][0]
            # Codex messages have "role" but might also use "function_call" blocks
            if "role" in entry:
                return True
    return False


def _parse_codex_transcript(data: dict[str, Any]) -> ParsedTranscript:
    """Parse a Codex/OpenAI transcript dict."""
    messages: list[dict] = data.get("messages") or []

    # If in chat completions format, extract from choices
    if "choices" in data:
        messages = []
        for choice in data["choices"]:
            if "message" in choice:
                messages.append(choice["message"])
            elif "delta" in choice:
                messages.append(choice["delta"])

    model = data.get("model")

    parsed_messages: list[ConversationEntry] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content is None:
            content = ""
        if isinstance(content, list):
            content = "\n".join(
                p.get("text", json.dumps(p)) if isinstance(p, dict) else str(p)
                for p in content
            )
        # Handle function calls
        if "function_call" in msg:
            fc = msg["function_call"]
            content += f"\n[Function call: {fc.get('name', 'unknown')}({fc.get('arguments', '')})]"
        parsed_messages.append(ConversationEntry(role=role, content=str(content)))

    return ParsedTranscript(
        agent_name="codex",
        model=model or None,
        messages=parsed_messages,
        raw=data,
    )


# ---------------------------------------------------------------------------
# Generic / fallback transcript
# ---------------------------------------------------------------------------

def _detect_generic_transcript(data: dict[str, Any]) -> bool:
    """Fallback: try to extract from any dict."""
    # Has a "messages" or "conversation" or "dialog" array
    for key in ("messages", "conversation", "dialog", "history", "chats"):
        if key in data and isinstance(data[key], list):
            return True
    return False


def _parse_generic_transcript(data: dict[str, Any]) -> ParsedTranscript:
    """Parse a generic transcript by looking for common structures."""
    messages: list[dict] = []

    for key in ("messages", "conversation", "dialog", "history", "chats"):
        if key in data and isinstance(data[key], list):
            messages = data[key]
            break

    parsed_messages: list[ConversationEntry] = []
    for msg in messages:
        if isinstance(msg, str):
            parsed_messages.append(ConversationEntry(role="user", content=msg))
        elif isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            parsed_messages.append(ConversationEntry(role=role, content=str(content)))

    return ParsedTranscript(
        agent_name="unknown",
        model=None,
        messages=parsed_messages,
        raw=data,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def import_transcript(path: Path | str) -> ParsedTranscript | None:
    """Import a transcript file, auto-detecting the format.

    Supports:
    * Claude Code (JSON with ``messages`` array)
    * Codex / OpenAI (JSON with ``choices`` or ``messages``)
    * Generic conversation JSON

    Returns ``None`` if the file cannot be read or parsed.
    """
    if isinstance(path, str):
        path = Path(path)

    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    if not isinstance(raw, dict):
        return None

    # Auto-detect format
    if _detect_claude_transcript(raw):
        return _parse_claude_transcript(raw)
    if _detect_codex_transcript(raw):
        return _parse_codex_transcript(raw)
    if _detect_generic_transcript(raw):
        return _parse_generic_transcript(raw)

    # Single conversation entry — wrap it
    return ParsedTranscript(
        agent_name="unknown",
        model=None,
        messages=[ConversationEntry(role="user", content=json.dumps(raw))],
        raw=raw,
    )


def format_transcript_summary(transcript: ParsedTranscript, max_entries: int = 5) -> str:
    """Format a parsed transcript into a short human-readable preview."""
    lines: list[str] = []
    lines.append(f"Agent: {transcript.agent_name}")
    if transcript.model:
        lines.append(f"Model: {transcript.model}")
    lines.append(f"Messages: {len(transcript.messages)}")
    lines.append("")

    shown = transcript.messages[:max_entries]
    for entry in shown:
        preview = entry.content[:120].replace("\n", " ")
        if len(entry.content) > 120:
            preview += "..."
        lines.append(f"[{entry.role}] {preview}")

    if len(transcript.messages) > max_entries:
        lines.append(f"... and {len(transcript.messages) - max_entries} more messages")

    return "\n".join(lines)
