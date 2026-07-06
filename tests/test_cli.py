import unittest

from backstory.cli import COMMANDS, RETRIEVAL_COMMANDS, _parse_line_spec, _parse_range_spec, build_parser


class CliTestCase(unittest.TestCase):
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
