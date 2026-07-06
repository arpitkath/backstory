from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path


@dataclass(frozen=True)
class GitRepositoryInfo:
    is_repository: bool
    root: Path | None


def inspect_repository(path: Path) -> GitRepositoryInfo:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return GitRepositoryInfo(is_repository=False, root=None)
    return GitRepositoryInfo(is_repository=True, root=Path(result.stdout.strip()))


def resolve_repo_root(path: Path) -> Path | None:
    return inspect_repository(path).root


def is_git_repository(path: Path) -> bool:
    return inspect_repository(path).is_repository
