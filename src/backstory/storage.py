from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


STORAGE_DIR_NAME = ".backstory"
OBJECTS_DIR_NAME = "objects"
SUMMARIES_DIR_NAME = "summaries"
PENDING_DIR_NAME = "pending"
REDACTIONS_DIR_NAME = "redactions"
INDEX_DB_NAME = "index.sqlite"


@dataclass(frozen=True)
class BackstoryPaths:
    root: Path
    objects: Path
    summaries: Path
    pending: Path
    redactions: Path
    index_db: Path


def build_storage_paths(repo_root: Path) -> BackstoryPaths:
    storage_root = repo_root / STORAGE_DIR_NAME
    return BackstoryPaths(
        root=storage_root,
        objects=storage_root / OBJECTS_DIR_NAME,
        summaries=storage_root / SUMMARIES_DIR_NAME,
        pending=storage_root / PENDING_DIR_NAME,
        redactions=storage_root / REDACTIONS_DIR_NAME,
        index_db=storage_root / INDEX_DB_NAME,
    )


def ensure_storage_layout(repo_root: Path) -> BackstoryPaths:
    paths = build_storage_paths(repo_root)
    paths.root.mkdir(exist_ok=True)
    paths.objects.mkdir(exist_ok=True)
    paths.summaries.mkdir(exist_ok=True)
    paths.pending.mkdir(exist_ok=True)
    paths.redactions.mkdir(exist_ok=True)
    return paths
