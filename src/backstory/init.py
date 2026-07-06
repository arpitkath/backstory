from __future__ import annotations

import json
import sys
from pathlib import Path

from backstory.config import DEFAULT_CONFIG, config_path, write_default_config
from backstory.hooks import hooks_installed, install_hooks
from backstory.storage import ensure_storage_layout


def initialize_repo(
    repo_root: Path,
    install_git_hooks: bool = True,
    force: bool = False,
) -> dict:
    """Initialize backstory in a Git repository.

    Steps:
        1. Validate the path is inside a Git repository.
        2. Create the ``.backstory/`` storage layout.
        3. Write a default ``config.json`` (preserves existing if ``force`` is False).
        4. Optionally install Git hooks.
        5. Return a status dict with results of each step.

    Parameters
    ----------
    repo_root:
        Root of the Git repository (from ``git rev-parse --show-toplevel``).
    install_git_hooks:
        Whether to install pre-commit and post-commit hooks.
    force:
        If True, overwrite existing config and reinstall hooks even if already set up.

    Returns
    -------
    A dict with keys ``storage_created``, ``config_written``, ``hooks_installed``.
    """
    result: dict = {}

    # --- storage ---
    paths = ensure_storage_layout(repo_root)
    result["storage_created"] = all(
        p.is_dir()
        for p in [paths.root, paths.objects, paths.summaries, paths.pending, paths.redactions]
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

    return result


def print_init_summary(repo_root: Path, result: dict) -> None:
    """Print a human-readable init summary to stdout."""
    print(f"✓ backstory initialized in {repo_root}")
    print()

    if result["storage_created"]:
        print("  Storage:  .backstory/ (objects, summaries, pending, redactions)")
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

    print()
    print("Next steps:")
    print("  1. Use an AI coding agent to make changes")
    print("  2. Run:  backstory dump --agent claude --transcript <path>")
    print("  3. Commit as usual:  git add . && git commit -m \"...\"")
    print("  4. Later: backstory why HEAD")
