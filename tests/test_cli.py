import unittest

from agent_why.cli import COMMANDS, build_parser


class CliTestCase(unittest.TestCase):
    def test_cli_exposes_core_commands(self):
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        self.assertEqual(sorted(subparsers.choices), sorted(COMMANDS))


if __name__ == "__main__":
    unittest.main()
