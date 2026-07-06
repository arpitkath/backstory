import subprocess
import tempfile
import unittest
from pathlib import Path

from backstory.git import inspect_repository, is_git_repository, resolve_repo_root
from backstory.storage import BackstoryPaths, build_storage_paths, ensure_storage_layout


class StorageTestCase(unittest.TestCase):
    def test_build_storage_paths_uses_repo_root_knowledge_layout(self):
        repo_root = Path("/tmp/example-repo")

        self.assertEqual(
            build_storage_paths(repo_root),
            BackstoryPaths(
                root=repo_root / ".backstory",
                knowledge=repo_root / ".backstory" / "knowledge",
                sessions=repo_root / ".backstory" / "knowledge" / "sessions",
                pending=repo_root / ".backstory" / "knowledge" / "sessions" / "latest.md",
                transcripts=repo_root / ".backstory" / "transcripts",
                redactions=repo_root / ".backstory" / "redactions",
                knowledge_index=repo_root / ".backstory" / "knowledge" / "index.md",
                sessions_index=repo_root / ".backstory" / "knowledge" / "sessions" / "index.md",
            ),
        )

    def test_ensure_storage_layout_creates_expected_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            paths = ensure_storage_layout(repo_root)

            self.assertTrue(paths.root.is_dir())
            self.assertTrue(paths.knowledge.is_dir())
            self.assertTrue(paths.sessions.is_dir())
            self.assertTrue(paths.transcripts.is_dir())
            self.assertTrue(paths.redactions.is_dir())


class GitHelpersTestCase(unittest.TestCase):
    def test_resolve_repo_root_returns_top_level_for_nested_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            nested = repo_root / "src" / "backstory"
            nested.mkdir(parents=True)
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)

            info = inspect_repository(nested)
            self.assertTrue(info.is_repository)
            self.assertEqual(resolve_repo_root(nested), repo_root)
            self.assertTrue(is_git_repository(nested))

    def test_git_helpers_return_falsey_values_outside_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            self.assertFalse(is_git_repository(path))
            self.assertIsNone(resolve_repo_root(path))


if __name__ == "__main__":
    unittest.main()
