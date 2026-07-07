from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from backstory import redact as redact_module
from backstory import search as search_module
from backstory import why as why_module
from backstory.attach import attach_pending_to_commit
from backstory.contradiction import detect_potential_contradictions
from backstory.dump import capture_session, load_pending_session, save_pending_session
from backstory.dump import discover_transcript_path
from backstory.hooks import hooks_installed, install_hooks, uninstall_hooks
from backstory.init import initialize_repo, print_init_summary
from backstory.okf import parse_session_markdown, render_session_markdown, session_id_to_filename
from backstory.retrieval import (
    commit_for_line,
    commits_for_file,
    commits_for_range,
    files_in_diff,
    format_retrieval_result,
    resolve_repo_root,
)
from backstory.storage import build_storage_paths, ensure_storage_layout
from backstory.summarize import summarize_transcript
from backstory.test_cmd import run_self_test
from backstory.transcript import (
    ExtractedDecisions,
    detect_agent_name,
    detect_model,
    format_decisions,
    import_transcript,
    normalize_messages,
)

COMMANDS = [
    "init",
    "dump",
    "attach",
    "why",
    "show",
    "search",
    "context",
    "test",
    "redact",
    "repair",
    "hooks",
    "session-end",
]

RETRIEVAL_COMMANDS = [
    "file",
    "line",
    "range",
    "diff",
    "code",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backstory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- init ---
    init_p = subparsers.add_parser("init", help="Initialize backstory in this repo")
    init_p.add_argument("--no-hooks", action="store_true", help="Skip Git hook installation")
    init_p.add_argument("--no-claude-settings", action="store_true", help="Skip .claude/settings.json creation")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing config, hooks, and claude settings")

    # --- dump ---
    dump_p = subparsers.add_parser("dump", help="Capture an AI session")
    dump_p.add_argument("--agent", default=None, help="Agent name (claude, codex)")
    dump_p.add_argument("--transcript", type=Path, default=None, help="Path to transcript JSON file")
    dump_p.add_argument("--task", default=None, help="Short task description")
    dump_p.add_argument("--hook", default=None, help=argparse.SUPPRESS)  # internal: called from hook

    # --- attach ---
    attach_p = subparsers.add_parser("attach", help="Attach pending session to a commit")
    attach_p.add_argument("commit_spec", nargs="?", default="HEAD", help="Commit hash or reference")
    attach_p.add_argument("--hook", default=None, help=argparse.SUPPRESS)  # internal

    # --- why ---
    why_p = subparsers.add_parser("why", help="Explain why a commit happened")
    why_p.add_argument("commit_spec", nargs="?", default="HEAD", help="Commit hash or reference")
    why_p.add_argument("--raw", action="store_true", help="Show raw session content")
    why_p.add_argument("--json", action="store_true", help="Output as JSON")

    # --- show ---
    subparsers.add_parser("show", help="Show a raw or structured session")

    # --- search ---
    search_p = subparsers.add_parser("search", help="Search stored AI sessions")
    search_p.add_argument("query", help="Search term")
    search_p.add_argument("--file", default=None, help="Filter by file path (glob)")
    search_p.add_argument("--branch", default=None, help="Filter by branch (glob)")
    search_p.add_argument("--max-results", type=int, default=10, help="Maximum results (default 10)")

    # --- context ---
    subparsers.add_parser("context", help="Show prior AI context for a file")

    # --- redact ---
    redact_p = subparsers.add_parser("redact", help="Redact secrets from sessions")
    redact_p.add_argument("session_id", nargs="?", default=None, help="Session ID to redact (default: pending)")

    # --- repair ---
    subparsers.add_parser("repair", help="Repair broken commit-session links")

    # --- hooks ---
    hooks_p = subparsers.add_parser("hooks", help="Manage Git hooks")
    hooks_sub = hooks_p.add_subparsers(dest="hooks_command", required=True)
    hooks_sub.add_parser("enable", help="Install backstory Git hooks")
    hooks_sub.add_parser("disable", help="Remove backstory Git hooks")
    hooks_sub.add_parser("status", help="Show hook installation status")

    # --- test ---
    subparsers.add_parser("test", help="Run self-test to verify installation and setup")

    # --- session-end ---
    subparsers.add_parser("session-end", help=argparse.SUPPRESS)  # internal: called from SessionEnd hook

    # --- retrieval commands ---
    file_p = subparsers.add_parser("file", help="Show commits affecting a file")
    file_p.add_argument("path", help="File path to query")

    line_p = subparsers.add_parser("line", help="Show what changed a specific line")
    line_p.add_argument("spec", help="path/to/file.py:42")

    range_p = subparsers.add_parser("range", help="Show commits affecting a line range")
    range_p.add_argument("spec", help="path/to/file.py:10-20")

    code_p = subparsers.add_parser("code", help="Alias for range")
    code_p.add_argument("spec", help="path/to/file.py:10-20")

    subparsers.add_parser("diff", help="Show prior context for uncommitted changes")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return _dispatch(args)


def _dispatch(args: argparse.Namespace) -> int:
    handler = _get_handler(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1
    return handler(args)


def _get_handler(command: str):
    return {
        "init": _handle_init,
        "dump": _handle_dump,
        "attach": _handle_attach,
        "why": _handle_why,
        "test": _handle_test,
        "search": _handle_search,
        "redact": _handle_redact,
        "hooks": _handle_hooks,
        "file": _handle_file,
        "line": _handle_line,
        "range": _handle_range,
        "code": _handle_range,
        "diff": _handle_diff,
        "session-end": _handle_session_end,
    }.get(command)


# ---------------------------------------------------------------------------
# why handler
# ---------------------------------------------------------------------------


def _handle_why(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    resolved = why_module.resolve_commit_spec(repo, args.commit_spec)
    if resolved is None:
        print(f"Commit not found: {args.commit_spec}", file=sys.stderr)
        return 1

    commit_hash, commit_message = resolved
    session = why_module.load_session_for_commit(repo, commit_hash)

    if session is None:
        print(f"No AI session found for commit {commit_hash}.")
        print("Sessions are linked to commits by running: backstory attach HEAD")
        return 0

    if args.json:
        import json
        print(json.dumps(session, indent=2, default=str))
        return 0

    output = why_module.format_why_output(session, commit_hash, commit_message)
    print(output)
    return 0


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# search handler
# ---------------------------------------------------------------------------


def _handle_search(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    matches = search_module.search_sessions(
        repo,
        args.query,
        file_filter=args.file,
        branch_filter=args.branch,
        max_results=args.max_results,
    )
    print(search_module.format_search_results(matches, args.query))
    return 0


# ---------------------------------------------------------------------------
# redact handler
# ---------------------------------------------------------------------------


def _handle_redact(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    paths = build_storage_paths(repo)

    if args.session_id:
        session_file = paths.sessions / session_id_to_filename(args.session_id)
        if not session_file.exists():
            print(f"Session not found: {args.session_id}", file=sys.stderr)
            return 1
        knowledge = parse_session_markdown(session_file.read_text(encoding="utf-8"))
        session = knowledge.to_session_dict()
    else:
        session = load_pending_session(repo)
        if session is None:
            print("No pending session to redact.", file=sys.stderr)
            return 1

    redacted, findings = redact_module.redact_session(session)

    if not findings:
        print("No secrets detected.")
        return 0

    print(f"Found {len(findings)} potential secret(s):")
    for f in findings:
        conf = f"{f.confidence:.0%}" if f.confidence >= 0 else "unknown"
        print(f"  - [{conf}] {f.pattern_name} in {f.context}")
    print()

    # Save redacted version
    old_id = session.get("session_id", "unknown")
    new_id = redacted.get("session_id", f"redacted-{old_id}")
    if new_id != old_id:
        redact_module.append_tombstone(repo, old_id, new_id)

    paths_new = ensure_storage_layout(repo)
    redacted_path = paths_new.sessions / session_id_to_filename(new_id)
    redacted_path.write_text(
        render_session_markdown(redacted), encoding="utf-8"
    )
    print(f"Redacted session saved: {redacted_path}")
    return 0


# ---------------------------------------------------------------------------
# hooks handler
# ---------------------------------------------------------------------------


def _handle_hooks(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    if args.hooks_command == "enable":
        written = install_hooks(repo)
        if len(written) == 2:
            print("✓ backstory Git hooks installed.")
        else:
            print(f"Installed {len(written)} hook(s) — expected 2.")
        return 0

    if args.hooks_command == "disable":
        removed = uninstall_hooks(repo)
        if removed > 0:
            print(f"✓ Removed {removed} backstory Git hook(s).")
        else:
            print("No backstory Git hooks found.")
        return 0

    if args.hooks_command == "status":
        status = hooks_installed(repo)
        pre = "✓ installed" if status.get("pre-commit") else "✗ not installed"
        post = "✓ installed" if status.get("post-commit") else "✗ not installed"
        print(f"Pre-commit hook:  {pre}")
        print(f"Post-commit hook: {post}")
        return 0

    print(f"Unknown hooks command: {args.hooks_command}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------


def _resolve_repo() -> Path | None:
    return resolve_repo_root(Path.cwd())


# ---------------------------------------------------------------------------
# init handler
# ---------------------------------------------------------------------------


def _handle_init(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        print("Run this command inside a Git repository.", file=sys.stderr)
        return 1

    result = initialize_repo(
        repo_root=repo,
        install_git_hooks=not args.no_hooks,
        force=args.force,
        install_claude_settings=not args.no_claude_settings,
    )
    print_init_summary(repo, result)
    return 0


# ---------------------------------------------------------------------------
# dump handler
# ---------------------------------------------------------------------------


def _handle_dump(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    # Resolve agent name
    agent_name = args.agent or "manual"
    model: str | None = None
    decisions = None

    transcript_path = args.transcript
    if transcript_path is None:
        transcript_path = discover_transcript_path(repo)
        if transcript_path is not None:
            print(f"Auto-detected transcript: {transcript_path}", file=sys.stderr)

    if transcript_path:
        # Step 1: Read the raw transcript file
        raw = import_transcript(transcript_path)
        if raw is None:
            print(f"Warning: could not read transcript from {transcript_path}", file=sys.stderr)
        else:
            # Step 2: Detect agent metadata from the transcript envelope
            agent_name = detect_agent_name(raw) or agent_name
            model = detect_model(raw)

            # Step 3: Normalize to message list
            messages = normalize_messages(raw)

            if messages:
                # Step 4: Ask the agent to summarize its own transcript
                print(f"Asking {agent_name} to summarize transcript...", file=sys.stderr)
                decisions = summarize_transcript(
                    messages=messages,
                    agent_name=agent_name,
                    model=model,
                )

                if decisions:
                    print(format_decisions(decisions))
                    print()
                else:
                    print(
                        "  (agent summarization unavailable — "
                        "install claude CLI for automatic extraction)",
                        file=sys.stderr,
                    )
                    # Still capture the session with basic info
                    decisions = ExtractedDecisions(
                        agent_name=agent_name,
                        model=model,
                        task=args.task or "",
                        decisions=[],
                    )
            else:
                print("Warning: no messages found in transcript", file=sys.stderr)

    # Override agent name from --agent flag if explicitly provided
    if args.agent:
        agent_name = args.agent

    # Capture session (NO raw conversation stored — only extracted decisions)
    session = capture_session(
        repo_root=repo,
        task=args.task,
        agent=agent_name,
        decisions=decisions,
    )

    path = save_pending_session(repo, session)
    print(f"Session saved: {session['session_id']}")
    print(f"Pending:       {path}")

    return 0


# ---------------------------------------------------------------------------
# attach handler
# ---------------------------------------------------------------------------


def _handle_attach(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    result = attach_pending_to_commit(repo, args.commit_spec)
    if result is None:
        if not args.hook:
            print("No pending session to attach.")
        return 0

    commit_hash = result.get("commit", {}).get("hash", args.commit_spec)
    print(f"Attached session {result['session_id']} to commit {commit_hash}")
    return 0


# ---------------------------------------------------------------------------
# file handler
# ---------------------------------------------------------------------------


def _handle_file(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    commits = commits_for_file(repo, args.path)
    output = format_retrieval_result(
        file_path=args.path,
        line_range=None,
        commits=commits,
    )
    print(output)
    return 0


# ---------------------------------------------------------------------------
# Parse helpers for line/range specs
# ---------------------------------------------------------------------------


def _parse_line_spec(spec: str) -> tuple[str, int] | None:
    """Parse 'path/to/file.py:42' into (path, 42)."""
    if ":" not in spec:
        return None
    parts = spec.rsplit(":", 1)
    try:
        return parts[0], int(parts[1])
    except (ValueError, IndexError):
        return None


def _parse_range_spec(spec: str) -> tuple[str, int, int] | None:
    """Parse 'path/to/file.py:10-20' into (path, 10, 20)."""
    if ":" not in spec or "-" not in spec:
        return None
    path_part, range_part = spec.rsplit(":", 1)
    if "-" not in range_part:
        return None
    try:
        start_str, end_str = range_part.split("-", 1)
        return path_part, int(start_str), int(end_str)
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# line / range / diff handlers
# ---------------------------------------------------------------------------


def _handle_line(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    parsed = _parse_line_spec(args.spec)
    if parsed is None:
        print("Invalid format. Use: backstory line <file>:<line>", file=sys.stderr)
        return 1

    path, line = parsed
    commit = commit_for_line(repo, path, line)
    commits = [commit] if commit else []
    output = format_retrieval_result(
        file_path=path,
        line_range=(line, line),
        commits=commits,
    )
    print(output)
    return 0


def _handle_range(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    parsed = _parse_range_spec(args.spec)
    if parsed is None:
        print("Invalid format. Use: backstory range <file>:<start>-<end>", file=sys.stderr)
        return 1

    path, start, end = parsed
    commits = commits_for_range(repo, path, start, end)
    output = format_retrieval_result(
        file_path=path,
        line_range=(start, end),
        commits=commits,
    )
    print(output)
    return 0


# ---------------------------------------------------------------------------
# test handler
# ---------------------------------------------------------------------------


def _handle_test(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    return run_self_test(repo)


def _handle_diff(args: argparse.Namespace) -> int:
    repo = _resolve_repo()
    if repo is None:
        print("Not in a Git repository.", file=sys.stderr)
        return 1

    changed_files = files_in_diff(repo)
    if not changed_files:
        print("No uncommitted changes detected.")
        return 0

    print("Relevant prior context for current diff:")
    print("")

    for idx, file_path in enumerate(changed_files, 1):
        commits = commits_for_file(repo, file_path)
        print(f"{idx}. {file_path}")
        if commits:
            print(f"   Most recent commit: {commits[0].hash} - {commits[0].message}")
            print(f"   Author: {commits[0].author}")
        else:
            print("   No previous commits found.")
        print()

    warnings = detect_potential_contradictions(repo, changed_files)
    if warnings:
        print("Potential contradictions:")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    return 0


def _handle_session_end(args: argparse.Namespace) -> int:
    """Handle the SessionEnd hook from Claude Code.

    Reads the transcript path from stdin (the real path Claude Code
    writes to), copies it to ``.backstory/transcripts/latest.jsonl``,
    then backgrounds ``backstory dump`` for heavy summarization.
    """
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("session-end hook: no JSON on stdin", file=sys.stderr)
        return 1

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        print("session-end hook: no transcript_path in stdin", file=sys.stderr)
        return 1

    src = Path(transcript_path)
    if not src.exists():
        print(f"session-end hook: transcript not found: {src}", file=sys.stderr)
        return 1

    repo_root = Path.cwd()
    target_dir = repo_root / ".backstory" / "transcripts"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy the transcript quickly (the sync part of the hook)
    target = target_dir / "latest.jsonl"
    shutil.copy2(src, target)
    print(f"Transcript copied to {target}", file=sys.stderr)

    # Background the heavy summarization — it survives the hook process exit
    subprocess.Popen(
        ["backstory", "dump"],
        cwd=repo_root,
        preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None,
    )

    return 0
