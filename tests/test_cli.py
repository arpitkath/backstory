import io
import sys
import unittest
from pathlib import Path

from backstory.cli import (
    COMMANDS,
    RETRIEVAL_COMMANDS,
    _parse_line_spec,
    _parse_range_spec,
    build_parser,
)


class CliParserTestCase(unittest.TestCase):
    def test_cli_exposes_core_commands(self):
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        all_commands = sorted(COMMANDS + RETRIEVAL_COMMANDS)
        self.assertEqual(sorted(subparsers.choices), all_commands)

    def test_new_retrieval_commands_present(self):
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        for cmd in ["file", "line", "range", "diff", "code"]:
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, subparsers.choices)

    def test_init_parser_accepts_flags(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--no-hooks", "--force"])
        self.assertTrue(args.no_hooks)
        self.assertTrue(args.force)

    def test_init_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["init"])
        self.assertFalse(args.no_hooks)
        self.assertFalse(args.force)

    def test_dump_parser_accepts_flags(self):
        parser = build_parser()
        args = parser.parse_args(["dump", "--agent", "claude", "--task", "Fix bug", "--transcript", "/tmp/t.json"])
        self.assertEqual(args.agent, "claude")
        self.assertEqual(args.task, "Fix bug")
        self.assertEqual(args.transcript, Path("/tmp/t.json"))

    def test_dump_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["dump"])
        self.assertIsNone(args.agent)
        self.assertIsNone(args.task)
        self.assertIsNone(args.transcript)

    def test_attach_parser_accepts_commit_spec(self):
        parser = build_parser()
        args = parser.parse_args(["attach", "HEAD"])
        self.assertEqual(args.commit_spec, "HEAD")

    def test_attach_parser_defaults_to_head(self):
        parser = build_parser()
        args = parser.parse_args(["attach"])
        self.assertEqual(args.commit_spec, "HEAD")

    # --- parse helpers ---

    def test_parse_line_spec_valid(self):
        result = _parse_line_spec("src/app.py:42")
        self.assertEqual(result, ("src/app.py", 42))

    def test_parse_line_spec_no_colon(self):
        self.assertIsNone(_parse_line_spec("src/app.py"))

    def test_parse_line_spec_non_int(self):
        self.assertIsNone(_parse_line_spec("src/app.py:abc"))

    def test_parse_range_spec_valid(self):
        result = _parse_range_spec("src/app.py:10-20")
        self.assertEqual(result, ("src/app.py", 10, 20))

    def test_parse_range_spec_no_hyphen(self):
        self.assertIsNone(_parse_range_spec("src/app.py:42"))

    def test_parse_range_spec_non_int(self):
        self.assertIsNone(_parse_range_spec("src/app.py:a-b"))


if __name__ == "__main__":
    unittest.main()
