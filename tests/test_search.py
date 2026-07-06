import subprocess
import tempfile
import unittest
from pathlib import Path

from backstory.okf import render_session_markdown, session_id_to_filename
from backstory.search import (
    SearchMatch,
    format_search_results,
    search_sessions,
)
from backstory.storage import ensure_storage_layout


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


class SearchTestCase(unittest.TestCase):
    """Tests for the search_sessions function."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)
        self.paths = ensure_storage_layout(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _write_session(self, session_dict: dict) -> Path:
        """Render a session dict to markdown and write it to the sessions dir.

        Returns the path to the written file.
        """
        markdown = render_session_markdown(session_dict)
        filename = session_id_to_filename(session_dict["session_id"])
        session_file = self.paths.sessions / filename
        session_file.write_text(markdown)
        return session_file

    def _make_session(self, **overrides) -> dict:
        """Return a minimal valid session dict with optional overrides."""
        session = {
            "version": "1.0",
            "session_id": "sha256:test123",
            "created_at": "2026-07-06T12:00:00Z",
            "repo": {"branch": "main", "head": "abc123"},
            "agent": {"name": "claude", "model": "sonnet", "source": "manual"},
            "task": {"title": "Fix bug", "user_prompt": ""},
            "files": {"changed": ["src/app.py"]},
            "diff": {"staged": "", "unstaged": ""},
            "reasoning_summary": {
                "why": "Fixed the payment bug",
                "decisions": ["Use webhook for retries"],
                "risks": ["Backfill needed"],
                "followups": ["Add monitoring"],
                "alternatives": [],
            },
            "commit": None,
        }
        session.update(overrides)
        return session

    # ------------------------------------------------------------------ #
    #  search_sessions
    # ------------------------------------------------------------------ #

    def test_search_sessions_empty_dir(self):
        """Empty sessions dir returns an empty list."""
        # Ensure the dir exists but has no session files.
        # ensure_storage_layout creates index.md and latest.md, which
        # _session_files skips, so the search surface is empty.
        result = search_sessions(self.repo_root, "bug")
        self.assertEqual(result, [])

    def test_search_sessions_no_match(self):
        """When no session contains the query, return an empty list."""
        self._write_session(self._make_session())
        result = search_sessions(self.repo_root, "nonexistent")
        self.assertEqual(result, [])

    def test_search_sessions_task_title_match(self):
        """Matching query in the task title returns a match with score >= 10."""
        s = self._make_session(
            session_id="sha256:titlematch",
            task={"title": "Fix payment bug", "user_prompt": ""},
            reasoning_summary={
                "why": "Fixed transaction logic",
                "decisions": ["Add retry mechanism"],
                "risks": ["May affect edge cases"],
                "followups": ["Add monitoring"],
                "alternatives": [],
            },
        )
        self._write_session(s)

        result = search_sessions(self.repo_root, "payment")
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0].score, 10)
        self.assertEqual(result[0].session_id, "sha256:titlematch")

    def test_search_sessions_decisions_match(self):
        """Matching query in the decisions section returns a match with score >= 8."""
        s = self._make_session(
            session_id="sha256:decisionmatch",
            task={"title": "Fix UI glitch", "user_prompt": ""},
            reasoning_summary={
                "why": "Addressed UI bugs",
                "decisions": ["Use webhook for retries"],
                "risks": ["Backfill needed"],
                "followups": ["Add monitoring"],
                "alternatives": [],
            },
        )
        self._write_session(s)

        result = search_sessions(self.repo_root, "webhook")
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0].score, 8)
        self.assertEqual(result[0].session_id, "sha256:decisionmatch")

    def test_search_sessions_risks_match(self):
        """Matching query in the risks section returns a match with score >= 5."""
        s = self._make_session(
            session_id="sha256:riskmatch",
            task={"title": "Fix UI glitch", "user_prompt": ""},
            reasoning_summary={
                "why": "Addressed UI bugs",
                "decisions": ["Use webhook for retries"],
                "risks": ["Backfill needed for old data"],
                "followups": ["Add monitoring"],
                "alternatives": [],
            },
        )
        self._write_session(s)

        result = search_sessions(self.repo_root, "backfill")
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0].score, 5)
        self.assertEqual(result[0].session_id, "sha256:riskmatch")

    def test_search_sessions_commit_message_match(self):
        """Matching query in the commit message returns a match with score > 0."""
        s = self._make_session(
            session_id="sha256:commitmatch",
            task={"title": "Refactor login", "user_prompt": ""},
            reasoning_summary={
                "why": "Refactored authentication flow",
                "decisions": ["Use OAuth"],
                "risks": ["Breaking change possible"],
                "followups": ["Update docs"],
                "alternatives": [],
            },
            commit={"hash": "def456", "message": "feat: add payment verification"},
            files={"changed": ["src/login.py"]},
        )
        self._write_session(s)

        result = search_sessions(self.repo_root, "verification")
        self.assertEqual(len(result), 1)
        self.assertGreater(result[0].score, 0)
        self.assertEqual(result[0].session_id, "sha256:commitmatch")

    def test_search_sessions_only_one_matches(self):
        """Multiple sessions, only one matches the query — returns exactly 1."""
        s1 = self._make_session(
            session_id="sha256:match001",
            task={"title": "Fix payment bug", "user_prompt": ""},
            reasoning_summary={
                "why": "Fixed transaction logic",
                "decisions": ["Add retry"],
                "risks": [],
                "followups": [],
                "alternatives": [],
            },
        )
        s2 = self._make_session(
            session_id="sha256:other002",
            task={"title": "Refactor cache layer", "user_prompt": ""},
            reasoning_summary={
                "why": "Improved cache invalidation",
                "decisions": [],
                "risks": [],
                "followups": [],
                "alternatives": [],
            },
        )
        self._write_session(s1)
        self._write_session(s2)

        result = search_sessions(self.repo_root, "payment")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].session_id, "sha256:match001")

    def test_search_sessions_file_filter_matches(self):
        """file_filter matching a changed file returns the session."""
        s1 = self._make_session(
            session_id="sha256:filematch",
            files={"changed": ["src/app.py", "src/utils.py"]},
        )
        s2 = self._make_session(
            session_id="sha256:fileother",
            files={"changed": ["tests/test_app.py"]},
        )
        self._write_session(s1)
        self._write_session(s2)

        # Both sessions contain "bug" in their title, but only s1 touches
        # "src/app.py".
        result = search_sessions(self.repo_root, "bug", file_filter="src/app.py")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].session_id, "sha256:filematch")

    def test_search_sessions_file_filter_no_match(self):
        """file_filter that does not match any changed file returns [].

        The session has "bug" in its title so it *would* match, but
        the file_filter excludes it.
        """
        s = self._make_session(
            session_id="sha256:fileexclude",
            files={"changed": ["src/app.py"]},
        )
        self._write_session(s)

        result = search_sessions(
            self.repo_root, "bug", file_filter="src/other.py"
        )
        self.assertEqual(result, [])

    def test_search_sessions_branch_filter_matches(self):
        """branch_filter matching the session's branch returns the session."""
        s1 = self._make_session(
            session_id="sha256:branchfeature",
            repo={"branch": "feature-x", "head": "abc123"},
        )
        s2 = self._make_session(
            session_id="sha256:branchmain",
            repo={"branch": "main", "head": "def456"},
        )
        self._write_session(s1)
        self._write_session(s2)

        result = search_sessions(
            self.repo_root, "bug", branch_filter="feature-x"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].session_id, "sha256:branchfeature")

    def test_search_sessions_branch_filter_no_match(self):
        """branch_filter that does not match returns [].

        The session has "bug" in its title so it *would* match, but
        the branch_filter excludes it.
        """
        s = self._make_session(
            session_id="sha256:branchexclude",
            repo={"branch": "main", "head": "abc123"},
        )
        self._write_session(s)

        result = search_sessions(
            self.repo_root, "bug", branch_filter="feature-x"
        )
        self.assertEqual(result, [])


class FormatSearchResultsTestCase(unittest.TestCase):
    """Tests for the format_search_results function."""

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _match(
        self,
        session_id: str = "sha256:abc123",
        commit_hash: str | None = "def456",
        commit_message: str | None = "Fix bug",
        task_title: str = "Fix payment bug",
        agent_name: str = "claude",
        created_at: str = "2026-07-06T12:00:00Z",
        snippet: str = "Use webhook for retries",
        file_path: str = "/sessions/sha256-abc123.md",
        score: float = 8.0,
    ) -> SearchMatch:
        return SearchMatch(
            session_id=session_id,
            commit_hash=commit_hash,
            commit_message=commit_message,
            task_title=task_title,
            agent_name=agent_name,
            created_at=created_at,
            snippet=snippet,
            file_path=file_path,
            score=score,
        )

    # ------------------------------------------------------------------ #
    #  Tests
    # ------------------------------------------------------------------ #

    def test_format_search_results_empty(self):
        """Empty match list produces a 'not found' message."""
        result = format_search_results([], "bug")
        self.assertEqual(result, "No sessions found matching 'bug'.")

    def test_format_search_results_empty_different_query(self):
        """The query is reflected in the 'not found' message."""
        result = format_search_results([], "authentication")
        self.assertEqual(
            result, "No sessions found matching 'authentication'."
        )

    def test_format_search_results_one_match(self):
        """A single match includes ID, Task, Agent, Date, Commit, Match."""
        m = self._match(
            session_id="sha256:abc123",
            commit_hash="def456",
            commit_message="Fix bug",
            task_title="Fix payment bug",
            agent_name="claude",
            created_at="2026-07-06T12:00:00Z",
            snippet="Use webhook for retries",
        )
        result = format_search_results([m], "bug")

        self.assertIn("Found 1 session(s)", result)
        self.assertIn("sha256:abc123", result)
        self.assertIn("Fix payment bug", result)
        self.assertIn("claude", result)
        self.assertIn("2026-07-06T12:00:00Z", result)
        self.assertIn("def456", result)
        self.assertIn("Fix bug", result)
        self.assertIn("Use webhook for retries", result)

    def test_format_search_results_one_match_no_commit(self):
        """A match without a commit skips the Commit line."""
        m = self._match(
            session_id="sha256:nocommit",
            commit_hash=None,
            commit_message=None,
            task_title="Fix UI glitch",
            snippet="Addressed UI bugs",
        )
        result = format_search_results([m], "UI")

        self.assertIn("sha256:nocommit", result)
        self.assertIn("Fix UI glitch", result)
        self.assertNotIn("Commit:", result)

    def test_format_search_results_multiple_matches(self):
        """Multiple matches are numbered."""
        m1 = self._match(
            session_id="sha256:first",
            task_title="Fix payment bug",
            snippet="Added retry logic",
        )
        m2 = self._match(
            session_id="sha256:second",
            task_title="Refactor auth",
            snippet="Switched to JWT",
        )
        result = format_search_results([m1, m2], "bug")

        self.assertIn("Found 2 session(s)", result)
        self.assertIn("1. sha256:first", result)
        self.assertIn("2. sha256:second", result)

    def test_format_search_results_order_matches_input(self):
        """Results appear in the order they are passed in."""
        m1 = self._match(
            session_id="sha256:aaa",
            task_title="First task",
            snippet="Alpha",
        )
        m2 = self._match(
            session_id="sha256:bbb",
            task_title="Second task",
            snippet="Beta",
        )
        m3 = self._match(
            session_id="sha256:ccc",
            task_title="Third task",
            snippet="Gamma",
        )
        result = format_search_results([m1, m2, m3], "task")

        self.assertIn("1. sha256:aaa", result)
        self.assertIn("2. sha256:bbb", result)
        self.assertIn("3. sha256:ccc", result)


if __name__ == "__main__":
    unittest.main()
