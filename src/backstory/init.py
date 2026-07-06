from __future__ import annotations

import json
import sys
from pathlib import Path

from backstory.config import DEFAULT_CONFIG, config_path, write_default_config
from backstory.hooks import hooks_installed, install_hooks
from backstory.storage import ensure_storage_layout


CLAUDE_SETTINGS_CONTENT = {
    "env": {
        "CLAUDE_TRANSCRIPT_PATH": ".backstory/transcripts/latest.json",
    },
}

# Known AI tool transcript env vars for status checking
AI_TRANSCRIPT_ENV_VARS = {
    "claude": "CLAUDE_TRANSCRIPT_PATH",
    "cursor": "CURSOR_TRANSCRIPT_PATH",
    "codex": "CODEX_TRANSCRIPT_PATH",
}

# Known AI tool settings file paths (relative to repo root)
AI_SETTINGS_FILES = {
    "claude": ".claude/settings.json",
    "cursor": ".cursor/settings.json",
}


def check_ai_settings(repo_root: Path) -> dict[str, bool | str]:
    """Check the status of AI tool integrations in the repository.

    Returns a dict keyed by tool name, where the value is:
    - ``True`` if the settings file exists with expected transcript path
    - ``"missing"`` if the settings file doesn't exist
    - ``"misconfigured"`` if the file exists but lacks expected env var
    """
    result: dict[str, bool | str] = {}

    for tool, rel_path in AI_SETTINGS_FILES.items():
        path = repo_root / rel_path
        if not path.exists():
            result[tool] = "missing"
            continue

        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            result[tool] = "misconfigured"
            continue

        env_var = AI_TRANSCRIPT_ENV_VARS.get(tool)
        env_config = content.get("env", {}) if isinstance(content, dict) else {}
        if isinstance(env_config, dict) and env_config.get(env_var) == ".backstory/transcripts/latest.json":
            result[tool] = True
        else:
            result[tool] = "misconfigured"

    return result


def initialize_repo(
    repo_root: Path,
    install_git_hooks: bool = True,
    force: bool = False,
    install_claude_settings: bool = True,
) -> dict:
    """Initialize backstory in a Git repository.

    Steps:
        1. Validate the path is inside a Git repository.
        2. Create the ``.backstory/`` storage layout (includes ``transcripts/``).
        3. Write a default ``config.json`` (preserves existing if ``force`` is False).
        4. Optionally install Git hooks.
        5. Optionally write ``.claude/settings.json`` with ``CLAUDE_TRANSCRIPT_PATH``.
        6. Return a status dict with results of each step.

    Parameters
    ----------
    repo_root:
        Root of the Git repository (from ``git rev-parse --show-toplevel``).
    install_git_hooks:
        Whether to install pre-commit and post-commit hooks.
    force:
        If True, overwrite existing config and reinstall hooks even if already set up.
    install_claude_settings:
        Whether to write ``.claude/settings.json`` for auto transcript capture.

    Returns
    -------
    A dict with keys ``storage_created``, ``config_written``, ``hooks_installed``,
    ``claude_settings_written``.
    """
    result: dict = {}

    # --- storage ---
    paths = ensure_storage_layout(repo_root)
    result["storage_created"] = all(
        p.is_dir()
        for p in [paths.root, paths.knowledge, paths.sessions, paths.transcripts, paths.redactions]
    )

    # --- config ---
    cfg_path = config_path(repo_root)
    if cfg_path.exists() and not force:
        result["config_written"] = False  # already exists, untouched
    else:
        write_default_config(repo_root)
        result["config_written"] = True

    # --- hooks ---
    if install_git_hooks:
        written = install_hooks(repo_root)
        result["hooks_installed"] = len(written) == 2
    else:
        status = hooks_installed(repo_root)
        result["hooks_installed"] = status.get("pre-commit", False) and status.get("post-commit", False)

    # --- .claude/settings.json ---
    if install_claude_settings:
        claude_dir = repo_root / ".claude"
        claude_settings_path = claude_dir / "settings.json"
        if claude_settings_path.exists() and not force:
            result["claude_settings_written"] = False
        else:
            claude_dir.mkdir(parents=True, exist_ok=True)
            claude_settings_path.write_text(
                json.dumps(CLAUDE_SETTINGS_CONTENT, indent=2) + "\n",
                encoding="utf-8",
            )
            result["claude_settings_written"] = True
    else:
        result["claude_settings_written"] = None

    return result


def print_init_summary(repo_root: Path, result: dict) -> None:
    """Print a human-readable init summary to stdout."""
    print(f"✓ backstory initialized in {repo_root}")
    print()

    if result["storage_created"]:
        print("  Storage:  .backstory/ (knowledge, sessions, transcripts, redactions)")
    else:
        print("  Storage:  error creating directories")

    if result["config_written"]:
        print("  Config:   .backstory/config.json written")
    else:
        print("  Config:   .backstory/config.json already exists (use --force to overwrite)")

    hooks = hooks_installed(repo_root)
    all_hooks = hooks.get("pre-commit", False) and hooks.get("post-commit", False)
    if all_hooks:
        print("  Hooks:    pre-commit + post-commit installed")
    elif any(hooks.values()):
        print("  Hooks:    partially installed (run --force to reinstall)")
    else:
        print("  Hooks:    none installed")

    cs = result.get("claude_settings_written")
    if cs is True:
        print("  Claude:   .claude/settings.json written (auto transcript capture)")
    elif cs is False:
        print("  Claude:   .claude/settings.json already exists (use --force to overwrite)")
    elif cs is None:
        print("  Claude:   skipped (--no-claude-settings)")

    print()
    print("Next steps:")
    print("  1. Use Claude Code to make changes (transcript auto-captured)")
    print("  2. Commit as usual:  git add . && git commit -m \"...\"")
    print("  3. Later: backstory why HEAD")
