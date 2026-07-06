from __future__ import annotations

import json
from pathlib import Path

from backstory.storage import (
    KNOWLEDGE_DIR_NAME,
    PENDING_SESSION_NAME,
    REDACTIONS_DIR_NAME,
    SESSIONS_DIR_NAME,
    STORAGE_DIR_NAME,
    ensure_storage_layout,
)


DEFAULT_CONFIG = {
    "storage": {
        "root": STORAGE_DIR_NAME,
        "knowledge_dir": KNOWLEDGE_DIR_NAME,
        "sessions_dir": SESSIONS_DIR_NAME,
        "pending_file": PENDING_SESSION_NAME,
        "redactions_dir": REDACTIONS_DIR_NAME,
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
