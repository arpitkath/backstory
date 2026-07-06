import subprocess
import tempfile
import unittest
from pathlib import Path

from backstory.okf import render_session_markdown, session_id_to_filename
from backstory.storage import build_storage_paths
from backstory.why import (
    format_why_output,
    load_session_for_commit,
    resolve_commit_spec,
)


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path, check=True, capture_output=True,
    )


def commit_file(path: Path, file_path: str, content: str, msg: str) -> None:
    full_path = path / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    subprocess.run(["git", "add", file_path], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=path, check=True, capture_output=True,
    )


def _make_session_dict(
    commit_hash: str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    session_id: str = "sha256:test-session",
    branch: str = "main",
    agent_name: str = "test-agent",
    task_title: str = "Test task",
    why: str = "",
    decisions: list[str] | None = None,
    risks: list[str] | None = None,
    followups: list[str] | None = None,
    files_changed: list[str] | None = None,
) -> dict:
    return {
        "version": "1.0",
        "session_id": session_id,
        "created_at": "2026-07-06T12:00:00Z",
        "repo": {"branch": branch, "head": commit_hash},
        "agent": {
            "name": agent_name,
            "model": "test-model",
            "source": "manual",
        },
        "task": {
            "title": task_title,
            "user_prompt": "",
        },
        "files": {
            "changed": files_changed or [],
        },
        "diff": {
            "staged": "",
            "unstaged": "",
        },
        "reasoning_summary": {
            "why": why,
            "decisions": decisions or [],
            "risks": risks or [],
            "followups": followups or [],
            "alternatives": [],
        },
        "commit": {
            "hash": commit_hash,
            "message": "Test commit",
        },
    }


def _write_session_file(
    repo_root: Path, session: dict, filename: str | None = None,
) -> Path:
    paths = build_storage_paths(repo_root)
    paths.sessions.mkdir(parents=True, exist_ok=True)
    if filename is None:
        sid = session.get("session_id", "unknown")
        filename = session_id_to_filename(sid)
    session_file = paths.sessions / filename
    session_file.write_text(render_session_markdown(session), encoding="utf-8")
    return session_file


# ---------------------------------------------------------------------------
# resolve_commit_spec
# ---------------------------------------------------------------------------

class ResolveCommitSpecTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_resolve_head_after_commit(self):
        commit_file(self.repo_root, "file.txt", "content\n", "Initial commit")
        result = resolve_commit_spec(self.repo_root, "HEAD")
        self.assertIsNotNone(result)
        commit_hash, commit_message = result  # type: ignore[misc]
        self.assertEqual(len(commit_hash), 40)
        self.assertEqual(commit_message, "Initial commit")

    def test_resolve_specific_hash(self):
        commit_file(self.repo_root, "a.txt", "hello\n", "First commit")
        commit_file(self.repo_root, "a.txt", "world\n", "Second commit")
        # Get the first commit's hash
        log = subprocess.run(
            ["git", "log", "--oneline", "--reverse"],
            cwd=self.repo_root, capture_output=True, text=True, check=True,
        )
        first_hash = log.stdout.strip().split("\n")[0].split()[0]
        result = resolve_commit_spec(self.repo_root, first_hash)
        self.assertIsNotNone(result)
        commit_hash, commit_message = result  # type: ignore[misc]
        self.assertEqual(commit_message, "First commit")

    def test_resolve_nonexistent_commit_returns_none(self):
        result = resolve_commit_spec(self.repo_root, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
        self.assertIsNone(result)

    def test_resolve_nonexistent_repo_returns_none(self):
        not_a_repo = self.repo_root / "not-a-repo"
        not_a_repo.mkdir()
        result = resolve_commit_spec(not_a_repo, "HEAD")
        self.assertIsNone(result)

    def test_resolve_outside_repo_returns_none(self):
        """A directory that exists but isn't a git repo at all."""
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp)
            result = resolve_commit_spec(outside, "HEAD")
            self.assertIsNone(result)

    def test_resolve_empty_repo_returns_none(self):
        """A freshly initialised repo with no commits."""
        result = resolve_commit_spec(self.repo_root, "HEAD")
        self.assertIsNone(result)

    def test_resolve_tag(self):
        tag = "v1.0"
        commit_file(self.repo_root, "f.txt", "data\n", "Tagged commit")
        subprocess.run(
            ["git", "tag", tag],
            cwd=self.repo_root, check=True, capture_output=True,
        )
        result = resolve_commit_spec(self.repo_root, tag)
        self.assertIsNotNone(result)
        _, commit_message = result  # type: ignore[misc]
        self.assertEqual(commit_message, "Tagged commit")


# ---------------------------------------------------------------------------
# format_why_output
# ---------------------------------------------------------------------------

class FormatWhyOutputTestCase(unittest.TestCase):
    def test_full_session_format(self):
        session = _make_session_dict(
            commit_hash="abcd1234" * 5,
            session_id="sha256:full-session",
            branch="feature-x",
            agent_name="claude",
            task_title="Add login feature",
            decisions=["Use JWT tokens", "Add refresh logic"],
            risks=["Token expiry needs migration"],
            followups=["Update docs"],
            files_changed=["auth/login.py", "auth/tokens.py"],
        )
        output = format_why_output(
            session, "abcd1234" * 5, "Add login feature",
        )
        # Required sections
        self.assertIn("Commit: abcd1234abcd1234abcd1234abcd1234abcd1234", output)
        self.assertIn("Message: Add login feature", output)
        self.assertIn("Branch: feature-x", output)
        self.assertIn("AI Agent: claude", output)
        self.assertIn("Session: sha256:full-session", output)
        self.assertIn("Task:", output)
        self.assertIn("Add login feature", output)
        # Optional present sections
        self.assertIn("Key decisions:", output)
        self.assertIn("  - Use JWT tokens", output)
        self.assertIn("  - Add refresh logic", output)
        self.assertIn("Files changed:", output)
        self.assertIn("  - auth/login.py", output)
        self.assertIn("  - auth/tokens.py", output)
        self.assertIn("Risks:", output)
        self.assertIn("  - Token expiry needs migration", output)
        self.assertIn("Follow-ups:", output)
        self.assertIn("  - Update docs", output)
        # Raw session path
        self.assertIn("Raw session:", output)
        self.assertIn(".backstory/knowledge/sessions/sha256-full-session.md", output)

    def test_empty_session_dict_does_not_crash(self):
        output = format_why_output({}, "hash123", "")
        self.assertIn("Commit: hash123", output)
        self.assertIn("Message: ", output)
        self.assertIn("Branch: unknown", output)
        self.assertIn("AI Agent: unknown", output)
        self.assertIn("Session: unknown", output)
        self.assertIn("Task:", output)

    def test_none_values_do_not_crash(self):
        session = {
            "repo": {"branch": None, "head": None},
            "agent": {"name": None, "model": None, "source": None},
            "task": {"title": None, "user_prompt": None},
            "reasoning_summary": {
                "why": None,
                "decisions": None,
                "risks": None,
                "followups": None,
                "alternatives": None,
            },
            "files": {"changed": None},
            "session_id": None,
        }
        output = format_why_output(session, "abc123", "msg")
        self.assertIn("Branch: unknown", output)
        self.assertIn("AI Agent: unknown", output)
        self.assertIn("Task:", output)

    def test_empty_omits_decisions_risks_files(self):
        """When decisions/risks/followups/changed are empty lists, their
        sections must not appear in the output."""
        session = _make_session_dict()
        output = format_why_output(session, "h" * 40, "msg")
        self.assertNotIn("Key decisions:", output)
        self.assertNotIn("Files changed:", output)
        self.assertNotIn("Risks:", output)
        self.assertNotIn("Follow-ups:", output)

    def test_partial_session_missing_keys(self):
        """Keys that are expected to exist may be absent entirely."""
        session = {
            "session_id": "partial",
        }
        output = format_why_output(session, "abc", "hi")
        self.assertIn("Branch: unknown", output)
        self.assertIn("AI Agent: unknown", output)
        self.assertIn("Task:", output)
        self.assertIn("Raw session:", output)

    def test_fallback_to_why_when_task_title_empty(self):
        session = _make_session_dict(task_title="", why="Fixed the timeout bug")
        output = format_why_output(session, "aaa", "msg")
        self.assertIn("Fixed the timeout bug", output)

    def test_fallback_to_no_task_description_when_both_empty(self):
        session = _make_session_dict(task_title="", why="")
        output = format_why_output(session, "bbb", "msg")
        self.assertIn("(no task description)", output)

    def test_decisions_section_appears_alone(self):
        """Only decisions present; other optional sections must be absent."""
        session = _make_session_dict(decisions=["Only decision"])
        output = format_why_output(session, "ccc", "msg")
        self.assertIn("Key decisions:", output)
        self.assertIn("  - Only decision", output)
        self.assertNotIn("Files changed:", output)
        self.assertNotIn("Risks:", output)
        self.assertNotIn("Follow-ups:", output)

    def test_files_section_appears_alone(self):
        session = _make_session_dict(files_changed=["only.py"])
        output = format_why_output(session, "ddd", "msg")
        self.assertNotIn("Key decisions:", output)
        self.assertIn("Files changed:", output)
        self.assertIn("  - only.py", output)
        self.assertNotIn("Risks:", output)
        self.assertNotIn("Follow-ups:", output)

    def test_all_optional_sections_present(self):
        session = _make_session_dict(
            decisions=["d1"],
            risks=["r1"],
            followups=["f1"],
            files_changed=["x.py"],
        )
        output = format_why_output(session, "eee", "msg")
        self.assertIn("Key decisions:", output)
        self.assertIn("Files changed:", output)
        self.assertIn("Risks:", output)
        self.assertIn("Follow-ups:", output)

    def test_raw_session_path_uses_session_id(self):
        session = _make_session_dict(session_id="my:custom:id")
        output = format_why_output(session, "fff", "msg")
        expected = ".backstory/knowledge/sessions/my-custom-id.md"
        self.assertIn(expected, output)

    def test_section_header_order(self):
        """Check that the main header lines appear in the expected order."""
        session = _make_session_dict(decisions=["d"], files_changed=["f"], risks=["r"], followups=["u"])
        output = format_why_output(session, "ggg", "m")
        # The stanza order is Commit, Message, Branch, AI Agent, Session
        self.assertLess(output.index("Commit:"), output.index("Message:"))
        self.assertLess(output.index("Message:"), output.index("Branch:"))
        self.assertLess(output.index("Branch:"), output.index("AI Agent:"))
        self.assertLess(output.index("AI Agent:"), output.index("Session:"))
        # Then Task, then the optional sections, then Raw session
        self.assertLess(output.index("Session:"), output.index("Task:"))
        self.assertLess(output.index("Task:"), output.index("Key decisions:"))
        self.assertLess(output.index("Key decisions:"), output.index("Files changed:"))
        self.assertLess(output.index("Files changed:"), output.index("Risks:"))
        self.assertLess(output.index("Risks:"), output.index("Follow-ups:"))
        self.assertLess(output.index("Follow-ups:"), output.index("Raw session:"))


# ---------------------------------------------------------------------------
# load_session_for_commit
# ---------------------------------------------------------------------------

class LoadSessionForCommitTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    # -- No session files exist -----------------------------------------------

    def test_no_session_files_returns_none(self):
        result = load_session_for_commit(
            self.repo_root, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        self.assertIsNone(result)

    # -- Session file exists with matching commit_hash -------------------------

    def test_matching_commit_hash_returns_session(self):
        commit_hash = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        session = _make_session_dict(commit_hash=commit_hash)
        _write_session_file(self.repo_root, session)
        result = load_session_for_commit(self.repo_root, commit_hash)
        self.assertIsNotNone(result)
        self.assertEqual(result["session_id"], session["session_id"])
        self.assertIsNotNone(result.get("commit"))
        self.assertEqual(result["commit"]["hash"], commit_hash)

    def test_matching_commit_hash_returns_full_session_dict(self):
        commit_hash = "cccccccccccccccccccccccccccccccccccccccc"
        session = _make_session_dict(
            commit_hash=commit_hash,
            task_title="Refactor auth",
            decisions=["Switch to JWT"],
            files_changed=["auth/jwt.py"],
        )
        _write_session_file(self.repo_root, session)
        result = load_session_for_commit(self.repo_root, commit_hash)
        self.assertIsNotNone(result)
        self.assertEqual(result["task"]["title"], "Refactor auth")
        self.assertIn("Switch to JWT", result["reasoning_summary"]["decisions"])
        self.assertIn("auth/jwt.py", result["files"]["changed"])

    # -- Session file exists without matching commit_hash ----------------------

    def test_non_matching_commit_hash_returns_none(self):
        session = _make_session_dict(
            commit_hash="dddddddddddddddddddddddddddddddddddddddd",
        )
        _write_session_file(self.repo_root, session)
        result = load_session_for_commit(
            self.repo_root, "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        )
        self.assertIsNone(result)

    def test_non_matching_among_multiple_sessions_returns_none(self):
        s1 = _make_session_dict(
            commit_hash="1111111111111111111111111111111111111111",
            session_id="sha256:sess-one",
        )
        s2 = _make_session_dict(
            commit_hash="2222222222222222222222222222222222222222",
            session_id="sha256:sess-two",
        )
        _write_session_file(self.repo_root, s1)
        _write_session_file(self.repo_root, s2)
        result = load_session_for_commit(
            self.repo_root, "3333333333333333333333333333333333333333",
        )
        self.assertIsNone(result)

    def test_matching_among_multiple_sessions_returns_correct_one(self):
        s1 = _make_session_dict(
            commit_hash="aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111",
            session_id="sha256:first-session",
            task_title="First task",
        )
        s2 = _make_session_dict(
            commit_hash="bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222",
            session_id="sha256:second-session",
            task_title="Second task",
        )
        _write_session_file(self.repo_root, s1)
        _write_session_file(self.repo_root, s2)
        result = load_session_for_commit(
            self.repo_root, "bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["session_id"], "sha256:second-session")
        self.assertEqual(result["task"]["title"], "Second task")

    # -- Non-existent sessions directory ---------------------------------------

    def test_nonexistent_sessions_dir_returns_none(self):
        """When the .backstory/knowledge/sessions/ directory doesn't exist,
        load_session_for_commit should return None."""
        result = load_session_for_commit(
            self.repo_root, "ffffffffffffffffffffffffffffffffffffffff",
        )
        self.assertIsNone(result)

    # -- Session directory exists but is empty ---------------------------------

    def test_empty_sessions_dir_returns_none(self):
        paths = build_storage_paths(self.repo_root)
        paths.sessions.mkdir(parents=True, exist_ok=True)
        result = load_session_for_commit(
            self.repo_root, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        self.assertIsNone(result)

    # -- latest.md is skipped --------------------------------------------------

    def test_latest_md_is_skipped(self):
        """The file named latest.md should be ignored during the scan."""
        commit_hash = "babababababababababababababababababababa"
        session = _make_session_dict(commit_hash=commit_hash)
        _write_session_file(self.repo_root, session, filename="latest.md")
        result = load_session_for_commit(self.repo_root, commit_hash)
        self.assertIsNone(result)

    # -- Session with no commit_hash in frontmatter ---------------------------

    def test_session_file_without_commit_hash_does_not_match(self):
        """A session file that has no commit_hash in its frontmatter should
        never match a non-None commit_hash query."""
        session = _make_session_dict(commit_hash="")
        # When commit_hash is empty string, the frontmatter omits commit_hash
        _write_session_file(self.repo_root, session)
        result = load_session_for_commit(
            self.repo_root, "0000000000000000000000000000000000000000",
        )
        self.assertIsNone(result)

    # -- Session file with corrupt / unparseable content -----------------------

    def test_corrupt_session_file_is_skipped(self):
        """A session file with invalid markdown is silently skipped."""
        paths = build_storage_paths(self.repo_root)
        paths.sessions.mkdir(parents=True, exist_ok=True)
        bad_file = paths.sessions / "corrupt.md"
        bad_file.write_text("this is not valid frontmatter", encoding="utf-8")
        result = load_session_for_commit(
            self.repo_root, "cccccccccccccccccccccccccccccccccccccccc",
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
