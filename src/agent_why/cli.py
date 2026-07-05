from __future__ import annotations

import argparse


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-why")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in COMMANDS:
        subparsers.add_parser(command)

    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0

