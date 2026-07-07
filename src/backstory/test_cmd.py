"""backstory test — verify the installation and repo setup."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from backstory.init import check_ai_settings
from backstory.hooks import hooks_installed
from backstory.storage import build_storage_paths
from backstory.dump import load_pending_session
from backstory.retrieval import files_in_diff, commits_for_file


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


def _ok(msg: str, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"{prefix}✅  {msg}")


def _warn(msg: str, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"{prefix}⚠️   {msg}")


def _fail(msg: str, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"{prefix}❌  {msg}")


def _header(title: str) -> None:
    print()
    print(f"── {title} {'─' * max(0, 60 - len(title) - 4)}")
    print()


def run_self_test(repo_root: Path) -> int:
    """Run all backstory diagnostic checks and return exit code."""
    passed = 0
    failed = 0
    warnings = 0

    print()
    print("╒════════════════════════════════════════════════════════╕")
    print("│         Backstory Self-Test                           │")
    print("╘════════════════════════════════════════════════════════╛")
    print(f"  Repo:  {repo_root}")

    # ------------------------------------------------------------------
    # 1. Git repo check
    # ------------------------------------------------------------------
    _header("1. Git Repository")
    result = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_root, check=False)
    if result.returncode == 0:
        _ok("Inside a Git repository")
        passed += 1
    else:
        _fail("Not inside a Git repository")
        failed += 1
        return 1

    branch_result = _run_git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, check=False
    )
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "?"
    _ok(f"Current branch: {branch}", indent=1)

    # ------------------------------------------------------------------
    # 2. Storage layout
    # ------------------------------------------------------------------
    _header("2. Storage Layout")
    paths = build_storage_paths(repo_root)

    checks = [
        ("root", paths.root.exists()),
        ("config", (paths.root / "config.json").exists()),
        ("knowledge", paths.knowledge.exists()),
        ("sessions", paths.sessions.exists()),
        ("transcripts", paths.transcripts.exists()),
    ]
    for label, ok in checks:
        if ok:
            _ok(f".backstory/{label}/", indent=1)
            passed += 1
        else:
            _fail(f".backstory/{label}/ — missing", indent=1)
            failed += 1

    # Warn if .backstory is gitignored (session data won't be tracked in VCS)
    gitignore = repo_root / ".gitignore"
    if gitignore.exists():
        try:
            for line in gitignore.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped in (".backstory", ".backstory/", ".backstory/**"):
                    _warn(".backstory/ is in .gitignore — session data won't be version-controlled", indent=1)
                    warnings += 1
                    break
                if stripped == "#":
                    break
        except OSError:
            pass

    # ------------------------------------------------------------------
    # 3. Git hooks
    # ------------------------------------------------------------------
    _header("3. Git Hooks")
    hook_status = hooks_installed(repo_root)
    for hook_name in ("pre-commit", "post-commit"):
        installed = hook_status.get(hook_name, False)
        if installed:
            _ok(f"{hook_name} hook installed", indent=1)
            passed += 1
        else:
            _warn(f"{hook_name} hook not installed", indent=1)
            warnings += 1

    # ------------------------------------------------------------------
    # 4. AI tool settings
    # ------------------------------------------------------------------
    _header("4. AI Tool Settings")
    ai_settings = check_ai_settings(repo_root)
    for tool in sorted(ai_settings):
        status = ai_settings[tool]
        if status is True:
            _ok(f"{tool.capitalize()} settings configured", indent=1)
            passed += 1
        elif status == "missing":
            _warn(f"{tool.capitalize()} settings not found", indent=1)
            warnings += 1
        elif status == "misconfigured":
            _warn(f"{tool.capitalize()} settings misconfigured", indent=1)
            warnings += 1

    # ------------------------------------------------------------------
    # 5. Pending session
    # ------------------------------------------------------------------
    _header("5. Pending Session")
    pending = load_pending_session(repo_root)
    if pending:
        _ok(f"Pending session found: {pending.get('session_id', '?')}", indent=1)
        passed += 1
    else:
        _ok("No pending session (clean state)", indent=1)
        passed += 1

    # ------------------------------------------------------------------
    # 6. Stored sessions
    # ------------------------------------------------------------------
    _header("6. Stored Sessions")
    if paths.sessions.exists():
        session_files = list(paths.sessions.glob("sha256-*.md"))
        count = len(session_files)
        _ok(f"{count} stored session(s)", indent=1)
        passed += 1
        if count > 0:
            # Show most recent
            latest = max(session_files, key=lambda p: p.stat().st_mtime)
            _ok(f"Most recent: {latest.name}", indent=2)
    else:
        _ok("No sessions directory yet", indent=1)
        passed += 1

    # ------------------------------------------------------------------
    # 7. Diff test
    # ------------------------------------------------------------------
    _header("7. Diff Test (prior context for uncommitted changes)")
    changed_files = files_in_diff(repo_root)
    if changed_files:
        _ok(f"{len(changed_files)} modified file(s) detected", indent=1)
        passed += 1
        for f in changed_files[:5]:
            commits = commits_for_file(repo_root, f)
            if commits:
                _ok(f"{f} — last touched in {commits[0].hash[:8]}", indent=2)
            else:
                _ok(f"{f} — no prior commits found", indent=2)
        if len(changed_files) > 5:
            _ok(f"... and {len(changed_files) - 5} more", indent=2)
    else:
        _ok("Working tree is clean", indent=1)
        passed += 1

    # ------------------------------------------------------------------
    # 8. Why HEAD test
    # ------------------------------------------------------------------
    _header("8. Why HEAD (last commit)")
    resolved = _run_git(
        ["log", "-1", "--format=%H%n%s", "HEAD"],
        cwd=repo_root,
        check=False,
    )
    if resolved.returncode == 0 and resolved.stdout.strip():
        lines = resolved.stdout.strip().split("\n", 1)
        commit_hash = lines[0].strip()
        commit_msg = lines[1].strip() if len(lines) > 1 else ""

        _ok(f"Last commit: {commit_hash[:12]} — {commit_msg}", indent=1)
        passed += 1

        # Check for attached session
        note_result = _run_git(
            ["notes", "--ref=refs/notes/backstory", "show", commit_hash],
            cwd=repo_root,
            check=False,
        )
        if note_result.returncode == 0 and note_result.stdout.strip():
            _ok("Session attached via Git notes", indent=1)
            passed += 1
        else:
            _warn("No AI session attached to HEAD yet", indent=1)
            warnings += 1
    else:
        _fail("Could not resolve HEAD commit", indent=1)
        failed += 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _header("9. Summary")
    total = passed + failed
    print(f"  Passed:     {passed}/{total}")
    print(f"  Warnings:   {warnings}")
    print(f"  Failed:     {failed}/{total}")
    print()

    if failed == 0:
        print("  ✅  All critical checks passed!")
    else:
        print(f"  ❌  {failed} critical check(s) failed — review issues above.")
        print()

    return 0 if failed == 0 else 1
