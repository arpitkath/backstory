import json
import tempfile
import unittest
from pathlib import Path

from backstory.transcript import (
    ExtractedDecisions,
    detect_agent_name,
    detect_model,
    format_decisions,
    import_transcript,
    normalize_messages,
)


class ImportTranscriptTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_import_valid_json(self):
        path = self.dir / "transcript.json"
        path.write_text(json.dumps({"messages": [{"role": "user", "content": "hi"}]}))
        result = import_transcript(path)
        self.assertIsNotNone(result)
        self.assertIn("messages", result)

    def test_import_nonexistent_file(self):
        result = import_transcript(self.dir / "missing.json")
        self.assertIsNone(result)

    def test_import_invalid_json(self):
        path = self.dir / "bad.json"
        path.write_text("not json")
        result = import_transcript(path)
        self.assertIsNone(result)

    def test_import_non_dict_json(self):
        path = self.dir / "array.json"
        path.write_text(json.dumps([1, 2, 3]))
        result = import_transcript(path)
        self.assertEqual(result, [1, 2, 3])  # returns raw parsed content


class NormalizeMessagesTestCase(unittest.TestCase):
    def test_claude_format(self):
        raw = {"messages": [{"role": "user", "content": "hello"}]}
        result = normalize_messages(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "hello")

    def test_conversation_format(self):
        raw = {"conversation": [{"role": "assistant", "content": "hi"}]}
        result = normalize_messages(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "assistant")

    def test_codex_choices_format(self):
        raw = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        result = normalize_messages(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "ok")

    def test_list_content_flattened(self):
        raw = {"messages": [{"role": "user", "content": [{"text": "a"}, {"text": "b"}]}]}
        result = normalize_messages(raw)
        self.assertIn("a", result[0]["content"])
        self.assertIn("b", result[0]["content"])

    def test_generic_dialog_fallback(self):
        raw = {"dialog": [{"role": "user", "content": "hey"}]}
        result = normalize_messages(raw)
        self.assertEqual(len(result), 1)

    def test_string_message_wrapped(self):
        raw = {"messages": ["hello", "world"]}
        result = normalize_messages(raw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "hello")

    def test_null_content_handled(self):
        raw = {"messages": [{"role": "user", "content": None}]}
        result = normalize_messages(raw)
        self.assertEqual(result[0]["content"], "")

    def test_empty_messages(self):
        raw = {"messages": []}
        result = normalize_messages(raw)
        self.assertEqual(result, [])

    def test_no_known_format(self):
        raw = {"unknown": True}
        result = normalize_messages(raw)
        self.assertEqual(result, [])


class DetectAgentNameTestCase(unittest.TestCase):
    def test_from_agent_block(self):
        raw = {"agent": {"name": "claude-code"}}
        self.assertEqual(detect_agent_name(raw), "claude-code")

    def test_from_model_claude(self):
        raw = {"model": "claude-sonnet-5"}
        self.assertEqual(detect_agent_name(raw), "claude-code")

    def test_from_model_codex(self):
        raw = {"model": "gpt-4"}
        self.assertEqual(detect_agent_name(raw), "codex")

    def test_unknown(self):
        raw = {"foo": "bar"}
        self.assertEqual(detect_agent_name(raw), "unknown")

    def test_custom_agent_name(self):
        raw = {"agent": {"name": "cursor"}}
        self.assertEqual(detect_agent_name(raw), "cursor")


class DetectModelTestCase(unittest.TestCase):
    def test_from_top_level(self):
        raw = {"model": "claude-sonnet-5"}
        self.assertEqual(detect_model(raw), "claude-sonnet-5")

    def test_from_agent_block(self):
        raw = {"agent": {"model": "gpt-4-turbo"}}
        self.assertEqual(detect_model(raw), "gpt-4-turbo")

    def test_none_when_missing(self):
        raw = {"foo": "bar"}
        self.assertIsNone(detect_model(raw))


class FormatDecisionsTestCase(unittest.TestCase):
    def test_format_all_sections(self):
        d = ExtractedDecisions(
            agent_name="claude-code",
            model="claude-sonnet",
            task="Refactor auth module",
            decisions=["Switch to JWT", "Add refresh tokens"],
            risks=["Token expiry needs migration"],
            followups=["Add token rotation docs"],
            files_changed=["auth/jwt.py", "auth/session.py"],
            alternatives=["Considered OAuth but chose JWT"],
        )
        output = format_decisions(d)
        self.assertIn("claude-code", output)
        self.assertIn("claude-sonnet", output)
        self.assertIn("Refactor auth", output)
        self.assertIn("JWT", output)
        self.assertIn("refresh tokens", output)
        self.assertIn("migration", output)
        self.assertIn("auth/jwt.py", output)
        self.assertIn("OAuth", output)

    def test_format_empty(self):
        d = ExtractedDecisions(agent_name="manual", model=None, task="")
        output = format_decisions(d)
        self.assertIn("Agent:", output)

    def test_format_truncates_long_lists(self):
        d = ExtractedDecisions(
            agent_name="test",
            model=None,
            task="Fix",
            decisions=[f"decision {i}" for i in range(30)],
            files_changed=[f"file_{i}.py" for i in range(20)],
        )
        output = format_decisions(d)
        self.assertIn("and 10 more", output)  # 30-20 = 10 more decisions
        self.assertIn("and 5 more", output)  # 20-15 = 5 more files


if __name__ == "__main__":
    unittest.main()
