from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SessionKnowledge:
    session_id: str
    created_at: str
    task_title: str
    user_prompt: str
    agent_name: str
    agent_model: str | None
    agent_source: str
    branch: str
    head: str
    commit_hash: str | None = None
    commit_message: str | None = None
    files_changed: list[str] = field(default_factory=list)
    staged_diff: str = ""
    unstaged_diff: str = ""
    why: str = ""
    decisions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)

    def to_session_dict(self) -> dict[str, Any]:
        commit = None
        if self.commit_hash:
            commit = {
                "hash": self.commit_hash,
                "message": self.commit_message or "",
            }

        return {
            "version": "1.0",
            "session_id": self.session_id,
            "created_at": self.created_at,
            "repo": {
                "branch": self.branch,
                "head": self.head,
            },
            "agent": {
                "name": self.agent_name,
                "model": self.agent_model,
                "source": self.agent_source,
            },
            "task": {
                "title": self.task_title,
                "user_prompt": self.user_prompt,
            },
            "files": {
                "changed": self.files_changed[:],
            },
            "diff": {
                "staged": self.staged_diff,
                "unstaged": self.unstaged_diff,
            },
            "reasoning_summary": {
                "why": self.why,
                "decisions": self.decisions[:],
                "risks": self.risks[:],
                "followups": self.followups[:],
                "alternatives": self.alternatives[:],
            },
            "commit": commit,
        }


def session_dict_to_knowledge(session: dict[str, Any]) -> SessionKnowledge:
    repo = session.get("repo", {})
    agent = session.get("agent", {})
    task = session.get("task", {})
    files = session.get("files", {})
    diff = session.get("diff", {})
    reasoning = session.get("reasoning_summary", {})
    commit = session.get("commit") or {}

    return SessionKnowledge(
        session_id=str(session.get("session_id", "")),
        created_at=str(session.get("created_at", "")),
        task_title=str(task.get("title", "")),
        user_prompt=str(task.get("user_prompt", "")),
        agent_name=str(agent.get("name", "manual")),
        agent_model=agent.get("model"),
        agent_source=str(agent.get("source", "manual")),
        branch=str(repo.get("branch", "unknown")),
        head=str(repo.get("head", "unknown")),
        commit_hash=commit.get("hash"),
        commit_message=commit.get("message"),
        files_changed=[str(path) for path in files.get("changed", []) if path],
        staged_diff=str(diff.get("staged", "")),
        unstaged_diff=str(diff.get("unstaged", "")),
        why=str(reasoning.get("why", "")),
        decisions=[str(item) for item in reasoning.get("decisions", []) if item],
        risks=[str(item) for item in reasoning.get("risks", []) if item],
        followups=[str(item) for item in reasoning.get("followups", []) if item],
        alternatives=[str(item) for item in reasoning.get("alternatives", []) if item],
    )


def render_session_markdown(session: dict[str, Any]) -> str:
    knowledge = session_dict_to_knowledge(session)
    return render_knowledge_markdown(knowledge)


def render_knowledge_markdown(knowledge: SessionKnowledge) -> str:
    lines: list[str] = []
    lines.append("---")
    lines.append("type: Backstory Session")
    lines.append(f"title: {knowledge.task_title or knowledge.why or 'Backstory Session'}")
    description = knowledge.why or knowledge.task_title or ""
    if description:
        lines.append(f"description: {description}")
    resource = f"git:{knowledge.commit_hash or knowledge.head}"
    lines.append(f"resource: {resource}")
    lines.append("tags: [backstory, ai-session]")
    lines.append(f"timestamp: {knowledge.created_at}")
    lines.append(f"session_id: {knowledge.session_id}")
    lines.append(f"agent: {knowledge.agent_name}")
    if knowledge.agent_model:
        lines.append(f"model: {knowledge.agent_model}")
    lines.append(f"source: {knowledge.agent_source}")
    lines.append(f"branch: {knowledge.branch}")
    lines.append(f"head: {knowledge.head}")
    if knowledge.commit_hash:
        lines.append(f"commit_hash: {knowledge.commit_hash}")
    if knowledge.commit_message:
        lines.append(f"commit_message: {knowledge.commit_message}")
    if knowledge.files_changed:
        lines.append("files_changed:")
        for path in knowledge.files_changed:
            lines.append(f"  - {path}")
    lines.append("---")
    lines.append("")

    _append_section(lines, "Task", knowledge.task_title)
    if knowledge.user_prompt and knowledge.user_prompt != knowledge.task_title:
        lines.append("")
        _append_section(lines, "User Prompt", knowledge.user_prompt)
    _append_list_section(lines, "Decisions", knowledge.decisions)
    _append_list_section(lines, "Risks", knowledge.risks)
    _append_list_section(lines, "Follow-ups", knowledge.followups)
    _append_list_section(lines, "Alternatives", knowledge.alternatives)
    _append_diff_section(lines, knowledge.staged_diff, knowledge.unstaged_diff)

    return "\n".join(lines).rstrip() + "\n"


def parse_session_markdown(text: str) -> SessionKnowledge:
    frontmatter, body = _split_frontmatter(text)
    meta = _parse_frontmatter(frontmatter)
    sections = _parse_body_sections(body)

    files_changed = _parse_string_list(meta.get("files_changed", []))
    task = sections.get("Task", "").strip()
    user_prompt = sections.get("User Prompt", "").strip() or task
    if not task:
        task = str(meta.get("title", ""))
    reasoning = {
        "why": str(meta.get("description", "")) or task,
        "decisions": _parse_section_list(sections.get("Decisions", "")),
        "risks": _parse_section_list(sections.get("Risks", "")),
        "followups": _parse_section_list(sections.get("Follow-ups", "")),
        "alternatives": _parse_section_list(sections.get("Alternatives", "")),
    }
    staged, unstaged = _parse_diff_section(sections.get("Diff", ""))

    commit_hash = meta.get("commit_hash")
    commit_message = meta.get("commit_message")

    return SessionKnowledge(
        session_id=str(meta.get("session_id", "")),
        created_at=str(meta.get("timestamp", "")),
        task_title=task,
        user_prompt=user_prompt,
        agent_name=str(meta.get("agent", "manual")),
        agent_model=meta.get("model"),
        agent_source=str(meta.get("source", "manual")),
        branch=str(meta.get("branch", "unknown")),
        head=str(meta.get("head", "unknown")),
        commit_hash=str(commit_hash) if commit_hash else None,
        commit_message=str(commit_message) if commit_message else None,
        files_changed=files_changed,
        staged_diff=staged,
        unstaged_diff=unstaged,
        why=reasoning["why"],
        decisions=reasoning["decisions"],
        risks=reasoning["risks"],
        followups=reasoning["followups"],
        alternatives=reasoning["alternatives"],
    )


def session_id_to_filename(session_id: str) -> str:
    return session_id.replace(":", "-") + ".md"


def _append_section(lines: list[str], title: str, content: str) -> None:
    lines.append(f"# {title}")
    lines.append("")
    lines.append(content.strip())


def _append_list_section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    for item in items:
        lines.append(f"- {item}")


def _append_diff_section(lines: list[str], staged: str, unstaged: str) -> None:
    if not staged and not unstaged:
        return
    lines.append("")
    lines.append("# Diff")
    lines.append("")
    lines.append("## Staged")
    lines.append("")
    lines.append("```diff")
    lines.append(staged.rstrip())
    lines.append("```")
    lines.append("")
    lines.append("## Unstaged")
    lines.append("")
    lines.append("```diff")
    lines.append(unstaged.rstrip())
    lines.append("```")


def _split_frontmatter(text: str) -> tuple[str, str]:
    stripped = text.lstrip()
    if not stripped.startswith("---\n"):
        return "", text
    remainder = stripped[4:]
    end = remainder.find("\n---\n")
    if end == -1:
        return "", text
    frontmatter = remainder[:end]
    body = remainder[end + 5 :]
    return frontmatter, body


def _parse_frontmatter(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            result.setdefault(current_list_key, []).append(line[4:].strip())
            continue
        current_list_key = None
        if line.endswith(":") and ": " not in line:
            key = line[:-1].strip()
            result[key] = []
            current_list_key = key
            continue
        if ": " in line:
            key, value = line.split(": ", 1)
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                result[key] = [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
            else:
                result[key] = value.strip()
    return result


def _parse_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _parse_body_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    in_code_block = False

    for raw_line in body.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("```"):
            if current is not None:
                sections.setdefault(current, []).append(line)
            in_code_block = not in_code_block
            continue
        if not in_code_block and line.startswith("# "):
            current = line[2:].strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)

    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _parse_section_list(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _parse_diff_section(text: str) -> tuple[str, str]:
    staged = ""
    unstaged = ""
    current: str | None = None
    buffer: list[str] = []
    in_code = False

    def flush() -> None:
        nonlocal staged, unstaged, buffer, current
        content = "\n".join(buffer).strip("\n")
        if current == "Staged":
            staged = content
        elif current == "Unstaged":
            unstaged = content
        buffer = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                flush()
            current = line[3:].strip()
            continue
        if line.startswith("```"):
            in_code = not in_code
            continue
        if current is not None:
            buffer.append(line)

    if current is not None:
        flush()

    return staged, unstaged
