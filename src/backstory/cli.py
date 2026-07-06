from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backstory.attach import attach_pending_to_commit
from backstory.dump import capture_session, save_pending_session
from backstory.init import initialize_repo, print_init_summary
from backstory.retrieval import (
    commit_for_line,
    commits_for_file,
    commits_for_range,
    files_in_diff,
    format_retrieval_result,
    resolve_repo_root,
)
from backstory.summarize import summarize_transcript
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
    "status",
    "redact",
    "repair",
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
    init_p.add_argument("--force", action="store_true", help="Overwrite existing config and hooks")

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

    # --- basic commands (no extra args yet) ---
    for name in ("why", "show", "search", "context", "status", "redact", "repair"):
        subparsers.add_parser(name)

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
        "file": _handle_file,
        "line": _handle_line,
        "range": _handle_range,
        "code": _handle_range,
        "diff": _handle_diff,
    }.get(command)


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

    if args.transcript:
        # Step 1: Read the raw transcript file
        raw = import_transcript(args.transcript)
        if raw is None:
            print(f"Warning: could not read transcript from {args.transcript}", file=sys.stderr)
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

    print(f"Attached session {result['session_id']} to commit {args.commit_spec}")
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

    return 0
