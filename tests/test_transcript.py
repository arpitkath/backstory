import json
import tempfile
import unittest
from pathlib import Path

from backstory.transcript import (
    _detect_claude_transcript,
    _detect_codex_transcript,
    _parse_claude_transcript,
    _parse_codex_transcript,
    format_transcript_summary,
    import_transcript,
)


class TranscriptClaudeTestCase(unittest.TestCase):
    def test_detect_claude_transcript_positive(self):
        data = {"messages": [{"role": "user", "content": "hello"}]}
        self.assertTrue(_detect_claude_transcript(data))

    def test_detect_claude_transcript_with_conversation(self):
        data = {"conversation": [{"role": "assistant", "content": "hi"}]}
        self.assertTrue(_detect_claude_transcript(data))

    def test_detect_claude_transcript_negative(self):
        data = {"foo": "bar"}
        self.assertFalse(_detect_claude_transcript(data))

    def test_parse_claude_transcript_extracts_messages(self):
        data = {
            "messages": [
                {"role": "user", "content": "Fix the bug"},
                {"role": "assistant", "content": "Here is the fix"},
            ],
            "model": "claude-sonnet-5",
        }
        parsed = _parse_claude_transcript(data)
        self.assertEqual(parsed.agent_name, "claude-code")
        self.assertEqual(parsed.model, "claude-sonnet-5")
        self.assertEqual(len(parsed.messages), 2)
        self.assertEqual(parsed.messages[0].role, "user")
        self.assertEqual(parsed.messages[1].content, "Here is the fix")

    def test_parse_claude_transcript_with_list_content(self):
        data = {
            "messages": [
                {"role": "user", "content": [{"text": "hello"}, {"text": "world"}]},
            ],
        }
        parsed = _parse_claude_transcript(data)
        self.assertIn("hello", parsed.messages[0].content)
        self.assertIn("world", parsed.messages[0].content)

    def test_parse_claude_transcript_empty(self):
        data = {"messages": []}
        parsed = _parse_claude_transcript(data)
        self.assertEqual(len(parsed.messages), 0)


class TranscriptCodexTestCase(unittest.TestCase):
    def test_detect_codex_transcript_positive_with_choices(self):
        data = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        self.assertTrue(_detect_codex_transcript(data))

    def test_detect_codex_transcript_with_messages(self):
        data = {"messages": [{"role": "user", "content": "hello"}]}
        self.assertTrue(_detect_codex_transcript(data))

    def test_detect_codex_transcript_negative(self):
        data = {"foo": "bar"}
        self.assertFalse(_detect_codex_transcript(data))

    def test_parse_codex_transcript_with_choices(self):
        data = {
            "model": "gpt-4",
            "choices": [
                {"message": {"role": "assistant", "content": "Here is code"}},
            ],
        }
        parsed = _parse_codex_transcript(data)
        self.assertEqual(parsed.agent_name, "codex")
        self.assertEqual(parsed.model, "gpt-4")
        self.assertEqual(len(parsed.messages), 1)
        self.assertEqual(parsed.messages[0].content, "Here is code")

    def test_parse_codex_transcript_with_function_call(self):
        data = {
            "messages": [
                {
                    "role": "assistant",
                    "content": "",
                    "function_call": {"name": "create_file", "arguments": "test.py"},
                },
            ],
        }
        parsed = _parse_codex_transcript(data)
        self.assertIn("create_file", parsed.messages[0].content)


class TranscriptImportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_import_claude_json(self):
        path = self.dir / "claude.json"
        path.write_text(
            json.dumps({"messages": [{"role": "user", "content": "hello"}]})
        )
        parsed = import_transcript(path)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.agent_name, "claude-code")  # type: ignore

    def test_import_codex_json(self):
        path = self.dir / "codex.json"
        path.write_text(
            json.dumps({"choices": [{"message": {"role": "assistant", "content": "hi"}}]})
        )
        parsed = import_transcript(path)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.agent_name, "codex")  # type: ignore

    def test_import_nonexistent_file(self):
        parsed = import_transcript(self.dir / "nonexistent.json")
        self.assertIsNone(parsed)

    def test_import_invalid_json(self):
        path = self.dir / "invalid.json"
        path.write_text("not json")
        parsed = import_transcript(path)
        self.assertIsNone(parsed)

    def test_import_returns_none_for_non_dict(self):
        path = self.dir / "array.json"
        path.write_text(json.dumps([1, 2, 3]))
        parsed = import_transcript(path)
        self.assertIsNone(parsed)


class TranscriptFormatTestCase(unittest.TestCase):
    def test_format_summary_includes_message_preview(self):
        transcript = _parse_claude_transcript(
            {
                "messages": [
                    {"role": "user", "content": "Hello world"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
                "model": "claude-sonnet",
            }
        )
        output = format_transcript_summary(transcript)
        self.assertIn("claude-code", output)
        self.assertIn("claude-sonnet", output)
        self.assertIn("Hello world", output)
        self.assertIn("Hi there", output)

    def test_format_summary_truncates_long_content(self):
        transcript = _parse_claude_transcript(
            {
                "messages": [
                    {"role": "user", "content": "x" * 300},
                ],
            }
        )
        output = format_transcript_summary(transcript)
        self.assertIn("...", output)

    def test_format_summary_shows_message_count(self):
        transcript = _parse_claude_transcript(
            {
                "messages": [
                    {"role": "user", "content": "a"},
                    {"role": "assistant", "content": "b"},
                    {"role": "user", "content": "c"},
                ],
            }
        )
        output = format_transcript_summary(transcript, max_entries=2)
        self.assertIn("3", output)  # total count
        self.assertIn("and 1 more", output)  # truncated


if __name__ == "__main__":
    unittest.main()
