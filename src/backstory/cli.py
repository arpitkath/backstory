from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backstory.retrieval import (
    commit_for_line,
    commits_for_file,
    commits_for_range,
    files_in_diff,
    format_retrieval_result,
    resolve_repo_root,
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

    for command in COMMANDS:
        subparsers.add_parser(command)

    # Add positional args for retrieval commands
    file_parser = subparsers.add_parser("file")
    file_parser.add_argument("path", help="File path to query")

    line_parser = subparsers.add_parser("line")
    line_parser.add_argument("spec", help="File and line (path/to/file.py:42)")

    range_parser = subparsers.add_parser("range")
    range_parser.add_argument("spec", help="File and range (path/to/file.py:10-20)")

    code_parser = subparsers.add_parser("code")
    code_parser.add_argument("spec", help="File and range (path/to/file.py:10-20)")

    subparsers.add_parser("diff")

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
    handlers = {
        "file": _handle_file,
        "line": _handle_line,
        "range": _handle_range,
        "code": _handle_range,
        "diff": _handle_diff,
    }
    return handlers.get(command)


def _resolve_repo() -> Path | None:
    return resolve_repo_root(Path.cwd())


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
