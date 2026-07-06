from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO


@dataclass(frozen=True)
class CommitInfo:
    hash: str
    message: str
    authored_at: str
    author: str


def _run_git(
    args: list[str], cwd: Path, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def resolve_repo_root(path: Path) -> Path | None:
    """Resolve the git repository root from an optional starting path."""
    result = _run_git(
        ["rev-parse", "--show-toplevel"], cwd=path, check=False
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def commits_for_file(repo_root: Path, file_path: str) -> list[CommitInfo]:
    """Find commits that touched a file using git log --follow.

    Returns most recent first.
    """
    result = _run_git(
        ["log", "--oneline", "--format=%H%n%an%n%aI%n%s%n---", "--follow", "--", file_path],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        return []
    return _parse_log_output(result.stdout)


def commit_for_line(repo_root: Path, file_path: str, line: int) -> CommitInfo | None:
    """Find the commit that last touched a specific line using git blame."""
    result = _run_git(
        ["blame", f"-L{line},{line}", "--porcelain", "--", file_path],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        return None
    return _parse_blame_commit(result.stdout, repo_root, file_path)


def commits_for_range(repo_root: Path, file_path: str, start: int, end: int) -> list[CommitInfo]:
    """Find distinct commits touching a line range using git blame."""
    result = _run_git(
        ["blame", f"-L{start},{end}", "--porcelain", "--", file_path],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        return []

    hashes = _extract_blame_hashes(result.stdout)
    if not hashes:
        return []

    # Get full details for each unique commit hash
    commits: list[CommitInfo] = []
    for h in hashes:
        info = _commit_info_by_hash(repo_root, h)
        if info:
            commits.append(info)

    # Sort by date descending (most recent first)
    commits.sort(key=lambda c: c.authored_at, reverse=True)
    return commits


def files_in_diff(repo_root: Path) -> list[str]:
    """Get list of changed files in the current working tree diff."""
    # Staged + unstaged changed files
    result = _run_git(
        ["diff", "--name-only", "HEAD"],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().split("\n") if f]


def format_retrieval_result(
    file_path: str | None,
    line_range: tuple[int, int] | None,
    commits: list[CommitInfo],
    linked_sessions: list[str] | None = None,
) -> str:
    """Format retrieval results for human-readable CLI output."""
    lines: list[str] = []

    if file_path:
        context = file_path
        if line_range:
            context += f":{line_range[0]}-{line_range[1]}"
        lines.append(f"Code context:")
        lines.append(context)
        lines.append("")

    if not commits:
        lines.append("No commits found for this code.")
        return "\n".join(lines)

    lines.append(f"Found {len(commits)} commit(s) affecting this code.")
    lines.append("")

    # Most relevant commit first
    lines.append(f"Most recent commit:")
    _append_commit(lines, commits[0])
    lines.append("")

    if len(commits) > 1:
        lines.append("Previous related commits:")
        for i, commit in enumerate(commits[1:], 1):
            _append_commit(lines, commit, prefix=f"{i}. ")
        lines.append("")

    if linked_sessions:
        lines.append("Linked AI sessions:")
        for sid in linked_sessions:
            lines.append(f"  - {sid}")
        lines.append("")

    return "\n".join(lines)


def _append_commit(
    lines: list[str], commit: CommitInfo, prefix: str = ""
) -> None:
    """Append formatted commit info to lines list."""
    lines.append(f"{prefix}{commit.hash} - {commit.message}")
    lines.append(f"   Author: {commit.author}")
    lines.append(f"   Date: {commit.authored_at}")


# --- Internal helpers ---


def _parse_log_output(output: str) -> list[CommitInfo]:
    """Parse git log output into structured commit info.

    Expected format per commit (from --format=%H%n%an%n%aI%n%s%n---):
    <hash>
    <author>
    <ISO date>
    <subject>
    ---
    """
    commits: list[CommitInfo] = []
    blocks = output.strip().split("\n---\n")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        if len(lines) < 4:
            continue
        commits.append(
            CommitInfo(
                hash=lines[0].strip(),
                author=lines[1].strip(),
                authored_at=lines[2].strip(),
                message=lines[3].strip(),
            )
        )
    return commits


def _parse_blame_commit(
    output: str, repo_root: Path, file_path: str
) -> CommitInfo | None:
    """Parse git blame --porcelain output into a single CommitInfo."""
    hashes = _extract_blame_hashes(output)
    if not hashes:
        return None
    return _commit_info_by_hash(repo_root, hashes[0])


def _extract_blame_hashes(output: str) -> list[str]:
    """Extract unique commit hashes from git blame --porcelain output.

    In porcelain mode each commit block starts with a line of the form:
        <40-char-hex-hash> <source-line> <result-line>
    """
    seen: set[str] = set()
    hashes: list[str] = []
    for line in output.split("\n"):
        if line.startswith("\t"):
            continue
        # Blame porcelain: each commit block starts with <hash> <line> <source-line>
        match = re.match(r"^([0-9a-f]{40}) \d+", line)
        if match and match.group(1) not in seen:
            seen.add(match.group(1))
            hashes.append(match.group(1))
    return hashes


def _commit_info_by_hash(repo_root: Path, commit_hash: str) -> CommitInfo | None:
    """Look up full commit info by hash."""
    result = _run_git(
        ["log", "-1", "--format=%H%n%an%n%aI%n%s", commit_hash],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().split("\n")
    if len(lines) < 4:
        return None
    return CommitInfo(
        hash=lines[0].strip(),
        author=lines[1].strip(),
        authored_at=lines[2].strip(),
        message=lines[3].strip(),
    )
