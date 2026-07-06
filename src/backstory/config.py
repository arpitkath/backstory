from __future__ import annotations

import json
from pathlib import Path

from backstory.storage import (
    INDEX_DB_NAME,
    OBJECTS_DIR_NAME,
    PENDING_DIR_NAME,
    REDACTIONS_DIR_NAME,
    STORAGE_DIR_NAME,
    SUMMARIES_DIR_NAME,
    ensure_storage_layout,
)


DEFAULT_CONFIG = {
    "version": 1,
    "storage": {
        "root": STORAGE_DIR_NAME,
        "objects_dir": OBJECTS_DIR_NAME,
        "summaries_dir": SUMMARIES_DIR_NAME,
        "pending_dir": PENDING_DIR_NAME,
        "redactions_dir": REDACTIONS_DIR_NAME,
        "index_db": INDEX_DB_NAME,
    },
    "capture": {
        "store_git_diff": True,
        "store_transcripts": True,
    },
    "redaction": {
        "enabled": True,
    },
}


def config_path(repo_root: Path) -> Path:
    return repo_root / ".backstory" / "config.json"


def write_default_config(repo_root: Path) -> Path:
    ensure_storage_layout(repo_root)
    path = config_path(repo_root)
    path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")
    return path


def load_config(repo_root: Path) -> dict:
    return json.loads(config_path(repo_root).read_text())
