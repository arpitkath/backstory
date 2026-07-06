import json
import unittest
from unittest.mock import MagicMock, patch

from backstory.transcript import ExtractedDecisions
from backstory.summarize import _parse_json_response, _render_messages


class ParseJsonResponseTestCase(unittest.TestCase):
    def test_parse_raw_json(self):
        text = '{"task": "fix bug", "decisions": ["added retry"]}'
        result = _parse_json_response(text)
        self.assertEqual(result["task"], "fix bug")
        self.assertEqual(result["decisions"], ["added retry"])

    def test_parse_json_in_code_fence(self):
        text = """Here's my analysis:
```json
{"task": "Refactor auth", "decisions": ["Switch to JWT"], "risks": []}
```
Done.
"""
        result = _parse_json_response(text)
        self.assertEqual(result["task"], "Refactor auth")

    def test_parse_json_in_backtick_fence(self):
        text = "```\n{\"task\": \"x\"}\n```"
        result = _parse_json_response(text)
        self.assertEqual(result["task"], "x")

    def test_parse_raises_on_non_dict(self):
        with self.assertRaises(ValueError):
            _parse_json_response("not json")

    def test_parse_raises_on_array(self):
        with self.assertRaises((ValueError, TypeError)):
            _parse_json_response("[1, 2, 3]")

    def test_parse_strips_markdown_wrapping(self):
        text = "**Result:**\n\n{\"task\": \"fix\", \"decisions\": []}"
        result = _parse_json_response(text)
        self.assertEqual(result["task"], "fix")


class RenderMessagesTestCase(unittest.TestCase):
    def test_renders_role_and_content(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        output = _render_messages(messages)
        self.assertIn("[user]", output)
        self.assertIn("[assistant]", output)
        self.assertIn("hello", output)
        self.assertIn("world", output)

    def test_truncates_long_content(self):
        messages = [{"role": "user", "content": "x" * 5000}]
        output = _render_messages(messages)
        self.assertIn("[truncated]", output)
        self.assertLess(len(output), 5000)

    def test_empty_messages(self):
        output = _render_messages([])
        self.assertEqual(output, "")


class SummarizeFlowTestCase(unittest.TestCase):
    """Integration-style tests with subprocess mocked."""

    @patch("backstory.summarize.subprocess.run")
    def test_summarize_parses_agent_response(self, mock_run):
        from backstory.summarize import summarize_transcript

        # Simulate a successful claude CLI response
        result_mock = MagicMock()
        result_mock.returncode = 0
        result_mock.stdout = json.dumps({
            "task": "Fix the login bug",
            "decisions": ["Added CSRF protection", "Updated validator"],
            "risks": ["Existing tokens invalidated"],
            "followups": [],
            "files_changed": ["app/login.py"],
            "alternatives": [],
        })
        mock_run.return_value = result_mock

        messages = [{"role": "user", "content": "Fix login"}]
        result = summarize_transcript(messages, agent_name="claude-code")

        self.assertIsNotNone(result)
        self.assertEqual(result.agent_name, "claude-code")  # type: ignore
        self.assertIn("CSRF", result.decisions[0])  # type: ignore

    @patch("backstory.summarize.subprocess.run")
    def test_summarize_returns_none_on_cli_failure(self, mock_run):
        from backstory.summarize import summarize_transcript

        mock_run.side_effect = FileNotFoundError()

        messages = [{"role": "user", "content": "Fix"}]
        result = summarize_transcript(messages, agent_name="claude-code")
        self.assertIsNone(result)

    def test_summarize_empty_messages(self):
        from backstory.summarize import summarize_transcript

        result = summarize_transcript([], agent_name="claude-code")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
