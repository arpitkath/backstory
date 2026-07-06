import subprocess
import tempfile
import unittest
from pathlib import Path

from backstory.git_notes import (
    NOTE_REF,
    list_noted_commits,
    read_git_note,
    remove_git_note,
    write_git_note,
)


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


def commit_file(path: Path, file_path: str, content: str, msg: str) -> str:
    full_path = path / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    subprocess.run(["git", "add", file_path], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=path, check=True, capture_output=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


class WriteGitNoteTestCase(unittest.TestCase):
    """Tests for write_git_note()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)
        self.commit_hash = commit_file(
            self.repo_root, "hello.py", "print('hello')", "Initial commit"
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    @property
    def valid_session(self) -> dict:
        return {
            "session_id": "sha256:abc123",
            "agent": {"name": "claude-code"},
            "created_at": "2026-07-05T12:00:00Z",
        }

    def test_write_note_to_commit_returns_true(self):
        result = write_git_note(self.repo_root, self.commit_hash, self.valid_session)
        self.assertTrue(result)

    def test_invalid_session_missing_session_id_returns_false(self):
        session = {"agent": {"name": "test"}, "created_at": "now"}
        result = write_git_note(self.repo_root, self.commit_hash, session)
        self.assertFalse(result)

    def test_invalid_session_empty_dict_returns_false(self):
        result = write_git_note(self.repo_root, self.commit_hash, {})
        self.assertFalse(result)

    def test_non_existent_commit_returns_false(self):
        # A string that cannot be resolved as a ref makes git notes add fail
        result = write_git_note(
            self.repo_root,
            "nonexistent-commit-hash",
            self.valid_session,
        )
        self.assertFalse(result)

    def test_write_note_without_agent_field_uses_unknown(self):
        session = {
            "session_id": "sha256:noagent",
            "created_at": "2026-07-05T12:00:00Z",
        }
        result = write_git_note(self.repo_root, self.commit_hash, session)
        self.assertTrue(result)

        note = read_git_note(self.repo_root, self.commit_hash)
        self.assertIsNotNone(note)
        self.assertEqual(note["agent"], "unknown")

    def test_write_note_without_created_at_uses_empty_string(self):
        session = {
            "session_id": "sha256:nodate",
            "agent": {"name": "test-agent"},
        }
        result = write_git_note(self.repo_root, self.commit_hash, session)
        self.assertTrue(result)

        note = read_git_note(self.repo_root, self.commit_hash)
        self.assertIsNotNone(note)
        self.assertEqual(note["created_at"], "")


class ReadGitNoteTestCase(unittest.TestCase):
    """Tests for read_git_note()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)
        self.commit_hash = commit_file(
            self.repo_root, "app.py", "print('ok')", "Initial commit"
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_write_then_read_returns_correct_dict(self):
        session = {
            "session_id": "sha256:abc123",
            "agent": {"name": "claude-code"},
            "created_at": "2026-07-05T12:00:00Z",
        }
        write_git_note(self.repo_root, self.commit_hash, session)

        note = read_git_note(self.repo_root, self.commit_hash)

        self.assertIsNotNone(note)
        self.assertEqual(note["ai_session"], "sha256:abc123")
        self.assertEqual(note["agent"], "claude-code")
        self.assertEqual(note["created_at"], "2026-07-05T12:00:00Z")

    def test_no_note_exists_returns_none(self):
        note = read_git_note(self.repo_root, self.commit_hash)
        self.assertIsNone(note)

    def test_after_removing_note_returns_none(self):
        session = {
            "session_id": "sha256:abc123",
            "agent": {"name": "claude"},
            "created_at": "now",
        }
        write_git_note(self.repo_root, self.commit_hash, session)
        remove_git_note(self.repo_root, self.commit_hash)

        note = read_git_note(self.repo_root, self.commit_hash)
        self.assertIsNone(note)

    def test_non_existent_repo_returns_none(self):
        non_repo = Path("/nonexistent_repo_12345")
        note = read_git_note(non_repo, "abc123")
        self.assertIsNone(note)

    def test_non_existent_commit_returns_none(self):
        note = read_git_note(
            self.repo_root, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        )
        self.assertIsNone(note)


class RemoveGitNoteTestCase(unittest.TestCase):
    """Tests for remove_git_note()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)
        self.commit_hash = commit_file(
            self.repo_root, "file.txt", "content", "Initial commit"
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_remove_existing_note_returns_true(self):
        session = {
            "session_id": "sha256:abc",
            "agent": {"name": "test"},
            "created_at": "now",
        }
        write_git_note(self.repo_root, self.commit_hash, session)

        result = remove_git_note(self.repo_root, self.commit_hash)
        self.assertTrue(result)

    def test_remove_non_existent_note_returns_false(self):
        result = remove_git_note(self.repo_root, self.commit_hash)
        self.assertFalse(result)

    def test_remove_non_existent_commit_returns_false(self):
        result = remove_git_note(
            self.repo_root, "0000000000000000000000000000000000000000"
        )
        self.assertFalse(result)

    def test_remove_note_twice_returns_false_second_time(self):
        session = {
            "session_id": "sha256:abc",
            "agent": {"name": "test"},
            "created_at": "now",
        }
        write_git_note(self.repo_root, self.commit_hash, session)

        self.assertTrue(remove_git_note(self.repo_root, self.commit_hash))
        self.assertFalse(remove_git_note(self.repo_root, self.commit_hash))

    def test_remove_in_non_existent_repo_returns_false(self):
        non_repo = Path("/nonexistent_repo_12345")
        result = remove_git_note(non_repo, "abc123")
        self.assertFalse(result)


class ListNotedCommitsTestCase(unittest.TestCase):
    """Tests for list_noted_commits()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_notes_returns_empty_list(self):
        commit_file(self.repo_root, "a.py", "a", "First commit")
        commits = list_noted_commits(self.repo_root)
        self.assertEqual(commits, [])

    def test_after_writing_one_note_returns_list_with_one_entry(self):
        hash1 = commit_file(self.repo_root, "a.py", "a", "First commit")
        session = {
            "session_id": "sha256:abc",
            "agent": {"name": "claude"},
            "created_at": "2026-07-05T12:00:00Z",
        }
        write_git_note(self.repo_root, hash1, session)

        commits = list_noted_commits(self.repo_root)

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0][0], hash1)
        self.assertEqual(commits[0][1]["ai_session"], "sha256:abc")

    def test_after_writing_multiple_notes_returns_all(self):
        hash1 = commit_file(self.repo_root, "a.py", "a", "First")
        hash2 = commit_file(self.repo_root, "b.py", "b", "Second")
        hash3 = commit_file(self.repo_root, "c.py", "c", "Third")

        write_git_note(self.repo_root, hash1, {
            "session_id": "sha256:aaa",
            "agent": {"name": "agent1"},
            "created_at": "t1",
        })
        write_git_note(self.repo_root, hash2, {
            "session_id": "sha256:bbb",
            "agent": {"name": "agent2"},
            "created_at": "t2",
        })
        write_git_note(self.repo_root, hash3, {
            "session_id": "sha256:ccc",
            "agent": {"name": "agent3"},
            "created_at": "t3",
        })

        commits = list_noted_commits(self.repo_root)

        self.assertEqual(len(commits), 3)
        noted_hashes = {c[0] for c in commits}
        noted_sessions = {c[1]["ai_session"] for c in commits}
        self.assertEqual(noted_hashes, {hash1, hash2, hash3})
        self.assertEqual(noted_sessions, {"sha256:aaa", "sha256:bbb", "sha256:ccc"})

    def test_non_existent_repo_returns_empty_list(self):
        non_repo = Path("/nonexistent_repo_12345")
        commits = list_noted_commits(non_repo)
        self.assertEqual(commits, [])

    def test_after_removing_note_list_excludes_it(self):
        hash1 = commit_file(self.repo_root, "a.py", "a", "First")
        hash2 = commit_file(self.repo_root, "b.py", "b", "Second")

        write_git_note(self.repo_root, hash1, {
            "session_id": "sha256:aaa",
            "agent": {"name": "a"},
            "created_at": "t1",
        })
        write_git_note(self.repo_root, hash2, {
            "session_id": "sha256:bbb",
            "agent": {"name": "b"},
            "created_at": "t2",
        })

        remove_git_note(self.repo_root, hash1)

        commits = list_noted_commits(self.repo_root)
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0][0], hash2)

    def test_list_returns_tuple_of_hash_and_dict(self):
        hash1 = commit_file(self.repo_root, "x.py", "x", "Commit")
        session = {
            "session_id": "sha256:xyz",
            "agent": {"name": "test-agent"},
            "created_at": "2026-07-05T12:00:00Z",
        }
        write_git_note(self.repo_root, hash1, session)

        commits = list_noted_commits(self.repo_root)

        self.assertEqual(len(commits), 1)
        commit_hash, note_dict = commits[0]
        self.assertIsInstance(commit_hash, str)
        self.assertIsInstance(note_dict, dict)
        self.assertEqual(commit_hash, hash1)
        self.assertEqual(note_dict["ai_session"], "sha256:xyz")
        self.assertEqual(note_dict["agent"], "test-agent")
        self.assertEqual(note_dict["created_at"], "2026-07-05T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
