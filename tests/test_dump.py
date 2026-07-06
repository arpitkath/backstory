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
from backstory.transcript import ExtractedDecisions


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
        self.assertIn("files", session)
        self.assertIn("diff", session)
        self.assertIn("reasoning_summary", session)
        # NO conversation data
        self.assertNotIn("conversation", session)
        self.assertEqual(session["version"], "1.0")

    def test_capture_session_no_raw_conversation_stored(self):
        """Verify that raw transcript content is NOT stored in the session."""
        decisions = ExtractedDecisions(
            agent_name="claude-code",
            model="claude-sonnet",
            task="Fix the login bug",
            decisions=["Added CSRF protection", "Updated token validation"],
            risks=["Existing tokens invalidated"],
            followups=["Update docs"],
            files_changed=["app/login.py"],
        )
        session = capture_session(
            repo_root=self.repo_root,
            agent="claude-code",
            decisions=decisions,
        )
        self.assertNotIn("conversation", session)
        # Summary has the extraction but not raw chat
        summary = session["reasoning_summary"]
        self.assertIn("CSRF", summary["decisions"][0])
        self.assertIn("invalidated", summary["risks"][0])

    def test_capture_session_stores_decisions_in_reasoning_summary(self):
        decisions = ExtractedDecisions(
            agent_name="claude-code",
            model="claude-sonnet-5",
            task="Refactor auth",
            decisions=["Switch to JWT", "Add refresh tokens"],
            risks=["Token expiry needs migration"],
            followups=["Add token rotation"],
            files_changed=["auth/jwt.py"],
        )
        session = capture_session(
            repo_root=self.repo_root,
            decisions=decisions,
        )
        summary = session["reasoning_summary"]
        self.assertEqual(summary["why"], "Refactor auth")
        self.assertEqual(summary["decisions"], ["Switch to JWT", "Add refresh tokens"])
        self.assertEqual(summary["risks"], ["Token expiry needs migration"])
        self.assertEqual(summary["followups"], ["Add token rotation"])

    def test_capture_session_merges_file_changes_from_git_and_decisions(self):
        decisions = ExtractedDecisions(
            agent_name="claude-code",
            model=None,
            task="Update billing",
            decisions=[],
            files_changed=["billing/webhook.py"],
        )
        session = capture_session(
            repo_root=self.repo_root,
            decisions=decisions,
        )
        # Git might not have changed files since no commits
        self.assertIn("billing/webhook.py", session["files"]["changed"])

    def test_capture_session_task_falls_back_to_why(self):
        decisions = ExtractedDecisions(
            agent_name="claude",
            model=None,
            task="Fix payment bug",
            decisions=["Added retry"],
        )
        session = capture_session(
            repo_root=self.repo_root,
            decisions=decisions,
        )
        self.assertEqual(session["task"]["title"], "Fix payment bug")

    def test_capture_session_agent_source_is_manual_by_default(self):
        session = capture_session(repo_root=self.repo_root, agent="codex")
        self.assertEqual(session["agent"]["name"], "codex")
        self.assertEqual(session["agent"]["source"], "manual")

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

    def test_session_has_no_conversation_key(self):
        """Double-check: session dict should never have a 'conversation' key."""
        session = capture_session(repo_root=self.repo_root, task="No chat")
        self.assertNotIn("conversation", session)
        self.assertNotIn("messages", session)


if __name__ == "__main__":
    unittest.main()
