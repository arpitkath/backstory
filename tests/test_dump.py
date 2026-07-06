import subprocess
import tempfile
import unittest
from pathlib import Path

from backstory.dump import (
    capture_session,
    clear_pending_session,
    load_pending_session,
    save_pending_session,
)
from backstory.transcript import _parse_claude_transcript


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path, check=True, capture_output=True,
    )


class DumpTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_capture_session_returns_expected_keys(self):
        session = capture_session(repo_root=self.repo_root, task="Fix bug")
        self.assertIn("session_id", session)
        self.assertIn("version", session)
        self.assertIn("created_at", session)
        self.assertIn("repo", session)
        self.assertIn("agent", session)
        self.assertIn("task", session)
        self.assertIn("conversation", session)
        self.assertIn("files", session)
        self.assertIn("diff", session)
        self.assertEqual(session["version"], "1.0")

    def test_capture_session_with_transcript(self):
        transcript = _parse_claude_transcript(
            {"messages": [{"role": "user", "content": "Hello"}]}
        )
        session = capture_session(
            repo_root=self.repo_root,
            agent="claude-code",
            transcript=transcript,
        )
        self.assertEqual(session["agent"]["name"], "claude-code")
        self.assertEqual(len(session["conversation"]), 1)
        self.assertEqual(session["conversation"][0]["role"], "user")

    def test_capture_session_uses_provided_agent(self):
        session = capture_session(repo_root=self.repo_root, agent="codex")
        self.assertEqual(session["agent"]["name"], "codex")

    def test_save_and_load_pending_session(self):
        session = capture_session(repo_root=self.repo_root, task="Test save")

        path = save_pending_session(self.repo_root, session)
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "latest.json")

        loaded = load_pending_session(self.repo_root)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["session_id"], session["session_id"])

    def test_load_pending_session_returns_none_when_missing(self):
        loaded = load_pending_session(self.repo_root)
        self.assertIsNone(loaded)

    def test_clear_pending_session_removes_file(self):
        session = capture_session(repo_root=self.repo_root)
        save_pending_session(self.repo_root, session)

        self.assertTrue(clear_pending_session(self.repo_root))
        self.assertIsNone(load_pending_session(self.repo_root))

    def test_clear_pending_session_returns_false_when_none(self):
        self.assertFalse(clear_pending_session(self.repo_root))


if __name__ == "__main__":
    unittest.main()
