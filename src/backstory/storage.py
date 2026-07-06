from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


STORAGE_DIR_NAME = ".backstory"
KNOWLEDGE_DIR_NAME = "knowledge"
SESSIONS_DIR_NAME = "sessions"
PENDING_SESSION_NAME = "latest.md"
REDACTIONS_DIR_NAME = "redactions"
INDEX_DB_NAME = "index.sqlite"
KNOWLEDGE_INDEX_NAME = "index.md"
SESSIONS_INDEX_NAME = "index.md"


@dataclass(frozen=True)
class BackstoryPaths:
    root: Path
    knowledge: Path
    sessions: Path
    pending: Path
    redactions: Path
    index_db: Path
    knowledge_index: Path
    sessions_index: Path


def build_storage_paths(repo_root: Path) -> BackstoryPaths:
    storage_root = repo_root / STORAGE_DIR_NAME
    knowledge_root = storage_root / KNOWLEDGE_DIR_NAME
    sessions_root = knowledge_root / SESSIONS_DIR_NAME
    return BackstoryPaths(
        root=storage_root,
        knowledge=knowledge_root,
        sessions=sessions_root,
        pending=sessions_root / PENDING_SESSION_NAME,
        redactions=storage_root / REDACTIONS_DIR_NAME,
        index_db=storage_root / INDEX_DB_NAME,
        knowledge_index=knowledge_root / KNOWLEDGE_INDEX_NAME,
        sessions_index=sessions_root / SESSIONS_INDEX_NAME,
    )


def ensure_storage_layout(repo_root: Path) -> BackstoryPaths:
    paths = build_storage_paths(repo_root)
    paths.root.mkdir(exist_ok=True)
    paths.knowledge.mkdir(exist_ok=True)
    paths.sessions.mkdir(exist_ok=True)
    paths.redactions.mkdir(exist_ok=True)
    _ensure_index_file(paths.knowledge_index, "# Backstory Knowledge\n")
    _ensure_index_file(paths.sessions_index, "# Backstory Sessions\n")
    return paths


def _ensure_index_file(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")
