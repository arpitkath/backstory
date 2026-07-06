from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from backstory.transcript import ExtractedDecisions

# ---------------------------------------------------------------------------
# Agent summarization prompts
# The agent reads its own transcript and returns only structured facts.
# ---------------------------------------------------------------------------

_SUMMARIZE_PROMPT = """You are a code-memory tool. A developer used an AI coding agent to make changes, and the conversation transcript is below.

Extract the factual decisions the agent made. Return ONLY a JSON object with these fields (no markdown, no explanation):

{
  "task": "short description of what the task was",
  "decisions": ["list of key technical decisions made"],
  "risks": ["risks or issues to be aware of"],
  "followups": ["follow-up tasks or known limitations"],
  "files_changed": ["list of file paths affected"],
  "alternatives": ["alternative approaches that were considered"]
}

Be concise. Use short, specific statements. Return valid JSON only.

TRANSCRIPT:
"""


def summarize_transcript(
    messages: list[dict[str, str]],
    agent_name: str,
    model: str | None = None,
) -> ExtractedDecisions | None:
    """Ask the AI agent to summarize its own transcript into structured decisions.

    The raw transcript is sent to the agent's CLI, and only the
    returned structured data (task, decisions, risks, files) is kept.

    Parameters
    ----------
    messages:
        Normalized list of ``{role, content}`` messages.
    agent_name:
        Which agent to invoke (``"claude-code"``, ``"codex"``, etc.).
    model:
        Optional model name to store in the result.

    Returns
    -------
    ``ExtractedDecisions`` with the agent's summary, or ``None`` if the
    agent CLI is unavailable or returns unparseable output.
    """
    if not messages:
        return None

    # Build the full prompt: system instructions + transcript
    transcript_text = _render_messages(messages)
    full_prompt = _SUMMARIZE_PROMPT + transcript_text

    # Dispatch to the right agent CLI
    if agent_name == "claude-code":
        result = _ask_claude(full_prompt)
    elif agent_name == "codex":
        result = _ask_codex(full_prompt)
    else:
        # Unknown agent — try claude as fallback, then return None
        result = _ask_claude(full_prompt)

    if result is None:
        return None

    # Parse the JSON response into ExtractedDecisions
    try:
        data = _parse_json_response(result)
    except (json.JSONDecodeError, ValueError):
        return None

    return ExtractedDecisions(
        agent_name=agent_name,
        model=model,
        task=data.get("task", ""),
        decisions=data.get("decisions", []),
        risks=data.get("risks", []),
        followups=data.get("followups", []),
        files_changed=data.get("files_changed", []),
        alternatives=data.get("alternatives", []),
    )


# ---------------------------------------------------------------------------
# Agent CLI invocation
# ---------------------------------------------------------------------------

CLAUDE_CLI_NAMES = ("claude", "claude-code")


def _ask_claude(prompt: str) -> str | None:
    """Invoke the Claude Code CLI to process a summarization prompt.

    Tries ``claude`` then ``claude-code``. Returns stdout on success,
    ``None`` if neither is installed or both fail.
    """
    for cmd in CLAUDE_CLI_NAMES:
        try:
            result = subprocess.run(
                [cmd, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            print("  (claude summarization timed out)", file=sys.stderr)
            return None
        except OSError:
            continue

    return None


def _ask_codex(prompt: str) -> str | None:
    """Invoke the Codex CLI if available (placeholder for now)."""
    # Codex doesn't have a standard CLI yet — try a generic fallback
    return _ask_claude(prompt)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract a JSON object from the agent's response.

    Handles responses wrapped in markdown code fences, wrapped in
    explanatory text, or raw JSON.
    """
    text = text.strip()

    # Always find the first { and last } — even with surrounding text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]

    if not text:
        raise ValueError("no JSON object found in response")

    parsed = json.loads(text)

    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")

    return parsed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _render_messages(messages: list[dict[str, str]]) -> str:
    """Render a list of messages into a plain-text transcript."""
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Truncate individual messages to avoid token limits
        if len(content) > 4000:
            content = content[:4000] + "\n...[truncated]"
        lines.append(f"[{role}]")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)
