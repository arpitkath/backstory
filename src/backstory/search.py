from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from backstory.okf import SessionKnowledge, parse_session_markdown
from backstory.storage import build_storage_paths


@dataclass
class SearchMatch:
    session_id: str
    commit_hash: str | None
    commit_message: str | None
    task_title: str
    agent_name: str
    created_at: str
    snippet: str  # Matching context snippet (first 200 chars around match)
    file_path: str  # Path to the session file
    score: float  # Simple relevance score (higher = better)


def search_sessions(
    repo_root: Path,
    query: str,
    *,
    file_filter: str | None = None,
    branch_filter: str | None = None,
    max_results: int = 10,
) -> list[SearchMatch]:
    """Search across all stored AI sessions in .backstory/knowledge/sessions/

    Strategies (apply all, deduplicate by session_id):
    1. **Frontmatter scan** -- Search session file frontmatter for query match
       (title, description, agent, branch, commit_message)
    2. **Body section scan** -- Search # Task, # Decisions, # Risks sections
    3. **Filename scan** -- Search session_id for query match

    Ranking (higher score = more relevant):
    - Query in task title: +10
    - Query in decisions: +8
    - Query in frontmatter description: +6
    - Query in risks/followups: +5
    - Query in filenames: +3
    - Query in commit message: +4

    Parameters
    ----------
    repo_root:
        Root of the Git repository.
    query:
        Search term to match (case-insensitive substring match).
    file_filter:
        Only return sessions that touched this file path.
    branch_filter:
        Only return sessions from this branch.
    max_results:
        Maximum number of results (default 10).
    """
    paths = build_storage_paths(repo_root)
    sessions_dir = paths.sessions

    if not sessions_dir.is_dir():
        return []

    query_lower = query.lower()
    seen: set[str] = set()
    matches: list[SearchMatch] = []

    for session_file in _session_files(sessions_dir):
        try:
            text = session_file.read_text(encoding="utf-8")
        except OSError:
            continue

        try:
            knowledge = parse_session_markdown(text)
        except Exception:
            continue

        # Apply filters before scoring.
        if file_filter and not _matches_file_filter(knowledge, file_filter):
            continue
        if branch_filter and not _matches_branch_filter(knowledge, branch_filter):
            continue

        # Skip duplicates by session_id.
        if knowledge.session_id in seen:
            continue
        seen.add(knowledge.session_id)

        score, snippet = _score_and_snippet(
            query_lower, text, knowledge, session_file
        )

        if score > 0:
            matches.append(
                SearchMatch(
                    session_id=knowledge.session_id,
                    commit_hash=knowledge.commit_hash,
                    commit_message=knowledge.commit_message,
                    task_title=knowledge.task_title,
                    agent_name=knowledge.agent_name,
                    created_at=knowledge.created_at,
                    snippet=snippet,
                    file_path=str(session_file),
                    score=score,
                )
            )

    # Sort by score descending, return top N.
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:max_results]


def format_search_results(matches: list[SearchMatch], query: str) -> str:
    """Format search results for human-readable CLI output.

    Parameters
    ----------
    matches:
        Search matches to format.
    query:
        Original search term (included in header / no-results message).
    """
    if not matches:
        return f"No sessions found matching '{query}'."

    lines: list[str] = []
    lines.append(f"Found {len(matches)} session(s) matching '{query}':")
    lines.append("")

    for i, m in enumerate(matches, 1):
        lines.append(f"{i}. {m.session_id}")
        lines.append(f"   Task: {m.task_title}")
        lines.append(f"   Agent: {m.agent_name} | Date: {m.created_at}")
        if m.commit_hash:
            msg = m.commit_message or ""
            lines.append(f"   Commit: {m.commit_hash} - {msg}")
        lines.append(f"   Match: {m.snippet}...")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _session_files(sessions_dir: Path) -> Iterator[Path]:
    """Yield regular session markdown files, skipping index.md and latest.md."""
    for path in sorted(sessions_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix != ".md":
            continue
        name = path.name
        if name in ("index.md", "latest.md"):
            continue
        yield path


def _matches_file_filter(knowledge: SessionKnowledge, file_filter: str) -> bool:
    """Check whether the session touched a file matching the filter.

    Supports glob-style patterns via fnmatch.
    """
    for changed in knowledge.files_changed:
        if fnmatch.fnmatch(changed, file_filter):
            return True
        if file_filter in changed:
            return True
    return False


def _matches_branch_filter(knowledge: SessionKnowledge, branch_filter: str) -> bool:
    """Check whether the session was recorded on a matching branch."""
    return (
        fnmatch.fnmatch(knowledge.branch, branch_filter)
        or branch_filter in knowledge.branch
    )


def _score_and_snippet(
    query_lower: str,
    full_text: str,
    knowledge: SessionKnowledge,
    session_file: Path,
) -> tuple[float, str]:
    """Score a session and extract a matching snippet.

    Returns (score, snippet_string).  Returns (0, "") when the query does not
    appear anywhere in the session.
    """
    score = 0.0
    match_location: str | None = None  # track the best-scoring line for the snippet

    frontmatter, body = _split_frontmatter(full_text)
    body_lower = body.lower()
    frontmatter_lower = frontmatter.lower()

    # --- Strategy 1: Frontmatter fields ---
    if query_lower in knowledge.task_title.lower():
        score += 10
        if match_location is None:
            match_location = knowledge.task_title
    if query_lower in knowledge.agent_name.lower():
        score += 6
        if match_location is None:
            match_location = knowledge.agent_name
    if query_lower in frontmatter_lower:
        # Generic frontmatter match (description, branch, etc.) -- +6
        # But check if it's specifically a commit_message match (extra).
        if knowledge.commit_message and query_lower in knowledge.commit_message.lower():
            score += 4
        else:
            score += 6
        if match_location is None:
            match_location = _extract_matching_line(frontmatter, query_lower)
    if knowledge.commit_message and query_lower in knowledge.commit_message.lower():
        # If commit_message was already scored above, don't double-count.
        # The above block already handles it.
        pass

    # --- Strategy 2: Body section scan ---
    if knowledge.decisions:
        decisions_text = "\n".join(knowledge.decisions)
        if query_lower in decisions_text.lower():
            score += 8
            if match_location is None:
                match_location = _extract_matching_line(decisions_text, query_lower)

    if knowledge.risks:
        risks_text = "\n".join(knowledge.risks)
        if query_lower in risks_text.lower():
            score += 5
            if match_location is None:
                match_location = _extract_matching_line(risks_text, query_lower)

    if knowledge.followups:
        followups_text = "\n".join(knowledge.followups)
        if query_lower in followups_text.lower():
            score += 5
            if match_location is None:
                match_location = _extract_matching_line(followups_text, query_lower)

    # --- Strategy 3: Filename scan ---
    if query_lower in knowledge.session_id.lower():
        score += 3
        if match_location is None:
            match_location = session_file.name

    # Check body sections not covered by structured fields (e.g. # Task, # User Prompt).
    if match_location is None and query_lower in body_lower:
        score += 1  # generic body match, low weight
        match_location = _extract_matching_line(body, query_lower)

    if score == 0:
        return 0.0, ""

    snippet = _build_snippet(match_location, query_lower)
    return score, snippet


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split session text into (frontmatter_string, body_string).

    Returns ("", full_text) if no valid frontmatter is found.
    """
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


def _extract_matching_line(text: str, query_lower: str) -> str:
    """Return the first line containing the query (case-insensitive)."""
    for line in text.splitlines():
        if query_lower in line.lower():
            return line.strip()
    return text[:200].strip()


def _build_snippet(match_location: str | None, query_lower: str) -> str:
    """Build a snippet of up to 200 characters centred on the match.

    If *match_location* is ``None`` or empty, returns an empty string.
    """
    if not match_location:
        return "???"

    match_lower = match_location.lower()
    pos = match_lower.find(query_lower)
    if pos == -1:
        # Fall back to start of string.
        return match_location[:200].strip()

    start = max(0, pos - 60)
    end = min(len(match_location), pos + len(query_lower) + 140)

    snippet = match_location[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(match_location):
        snippet = snippet + "..."

    return snippet[:200].strip()
