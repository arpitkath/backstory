import subprocess
import tempfile
import unittest
from pathlib import Path

from backstory.retrieval import (
    CommitInfo,
    _extract_blame_hashes,
    _parse_log_output,
    commit_for_line,
    commits_for_file,
    commits_for_range,
    files_in_diff,
    format_retrieval_result,
    resolve_repo_root,
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


class RetrievalTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_resolve_repo_root(self):
        nested = self.repo_root / "src" / "backstory"
        nested.mkdir(parents=True)
        self.assertEqual(resolve_repo_root(nested), self.repo_root)

    def test_resolve_repo_root_outside_repo(self):
        outside = Path("/tmp")
        self.assertIsNone(resolve_repo_root(outside))

    def test_commits_for_file_returns_commit_list(self):
        commit_file(self.repo_root, "hello.py", "print('hello')", "Initial commit")

        commits = commits_for_file(self.repo_root, "hello.py")

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].message, "Initial commit")

    def test_commits_for_file_ordered_most_recent_first(self):
        commit_file(self.repo_root, "hello.py", "v1\n", "First")
        commit_file(self.repo_root, "hello.py", "v2\n", "Second")

        commits = commits_for_file(self.repo_root, "hello.py")

        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].message, "Second")
        self.assertEqual(commits[1].message, "First")

    def test_commits_for_file_returns_empty_for_unknown_file(self):
        commits = commits_for_file(self.repo_root, "nonexistent.py")
        self.assertEqual(commits, [])

    def test_commit_for_line_returns_correct_commit(self):
        commit_file(self.repo_root, "app.py", "line1\nline2\nline3\n", "Initial")

        info = commit_for_line(self.repo_root, "app.py", 2)

        self.assertIsNotNone(info)
        self.assertEqual(info.message, "Initial")  # type: ignore

    def test_commit_for_line_returns_none_for_invalid_line(self):
        commit_file(self.repo_root, "app.py", "line1\n", "Initial")

        info = commit_for_line(self.repo_root, "app.py", 999)
        self.assertIsNone(info)

    def test_commit_for_line_returns_none_for_unknown_file(self):
        info = commit_for_line(self.repo_root, "missing.py", 1)
        self.assertIsNone(info)

    def test_commits_for_range_returns_distinct_commits(self):
        commit_file(self.repo_root, "range.py", "a\nb\nc\nd\ne\n", "First")
        commit_file(self.repo_root, "range.py", "a\nX\nc\nd\nZ\n", "Second")

        commits = commits_for_range(self.repo_root, "range.py", 1, 5)

        self.assertGreaterEqual(len(commits), 1)
        messages = {c.message for c in commits}
        self.assertIn("Second", messages)

    def test_commits_for_range_returns_empty_for_unknown_file(self):
        commits = commits_for_range(self.repo_root, "missing.py", 1, 10)
        self.assertEqual(commits, [])

    def test_files_in_diff_returns_changed_files(self):
        commit_file(self.repo_root, "base.py", "initial\n", "Base commit")
        # Now modify it unstaged
        (self.repo_root / "base.py").write_text("modified\n")

        files = files_in_diff(self.repo_root)

        self.assertIn("base.py", files)

    def test_files_in_diff_returns_empty_for_clean_repo(self):
        commit_file(self.repo_root, "clean.py", "ok\n", "Clean commit")

        files = files_in_diff(self.repo_root)
        self.assertEqual(files, [])

    def test_format_retrieval_result_with_commits(self):
        commits = [
            CommitInfo(hash="abc123", message="Fix bug", authored_at="2026-07-01T12:00:00Z", author="Test"),
        ]
        output = format_retrieval_result(
            file_path="src/app.py", line_range=(10, 20), commits=commits,
        )
        self.assertIn("src/app.py:10-20", output)
        self.assertIn("abc123", output)
        self.assertIn("Fix bug", output)
        self.assertIn("Test", output)

    def test_format_retrieval_result_no_commits(self):
        output = format_retrieval_result(
            file_path="src/unknown.py", line_range=None, commits=[],
        )
        self.assertIn("No commits found", output)
        self.assertIn("src/unknown.py", output)

    def test_format_retrieval_result_with_linked_sessions(self):
        commits = [
            CommitInfo(hash="abc123", message="Fix", authored_at="2026-07-01T12:00:00Z", author="Test"),
        ]
        output = format_retrieval_result(
            file_path="app.py", line_range=None, commits=commits,
            linked_sessions=["sha256:abc123", "sha256:def456"],
        )
        self.assertIn("sha256:abc123", output)
        self.assertIn("sha256:def456", output)
        self.assertIn("Linked AI sessions", output)


class ParseHelpersTestCase(unittest.TestCase):
    def test_parse_log_output_parses_single_commit(self):
        output = "abc123def4567890\nJohn Doe\n2026-07-01T12:00:00Z\nFix the bug\n---\n"
        commits = _parse_log_output(output)
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].hash, "abc123def4567890")
        self.assertEqual(commits[0].author, "John Doe")
        self.assertEqual(commits[0].authored_at, "2026-07-01T12:00:00Z")
        self.assertEqual(commits[0].message, "Fix the bug")

    def test_parse_log_output_parses_multiple_commits(self):
        output = (
            "aaa\nAlice\n2026-07-01T00:00:00Z\nFirst\n---\n"
            "bbb\nBob\n2026-07-02T00:00:00Z\nSecond\n---\n"
        )
        commits = _parse_log_output(output)
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].hash, "aaa")
        self.assertEqual(commits[1].hash, "bbb")

    def test_parse_log_output_handles_empty_output(self):
        commits = _parse_log_output("")
        self.assertEqual(commits, [])

    def test_extract_blame_hashes_from_porcelain_output(self):
        # Simulated git blame --porcelain output for 2 lines
        output = (
            "abc123def4567890abc123def4567890abc12345 1 1\n"
            "author John Doe\n"
            "author-mail <john@test.com>\n"
            "author-time 1700000000\n"
            "author-tz +0000\n"
            "committer John Doe\n"
            "committer-mail <john@test.com>\n"
            "committer-time 1700000000\n"
            "committer-tz +0000\n"
            "summary First commit\n"
            "previous 0000000000000000000000000000000000000000 deadbeef\n"
            "filename test.py\n"
            "\tprint('hello')\n"
            "deadbeef1234567890deadbeef1234567890dead 2 2\n"
            "\tprint('world')\n"
        )
        hashes = _extract_blame_hashes(output)
        self.assertIn("abc123def4567890abc123def4567890abc12345", hashes)
        self.assertIn("deadbeef1234567890deadbeef1234567890dead", hashes)

    def test_extract_blame_hashes_handles_empty(self):
        hashes = _extract_blame_hashes("")
        self.assertEqual(hashes, [])


if __name__ == "__main__":
    unittest.main()
