import subprocess
import tempfile
import unittest
from pathlib import Path

from backstory.init import initialize_repo, print_init_summary
from backstory.hooks import hooks_installed


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


class InitTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_init_creates_backstory_storage(self):
        result = initialize_repo(self.repo_root)

        self.assertTrue(result["storage_created"])
        self.assertTrue((self.repo_root / ".backstory").is_dir())
        self.assertTrue((self.repo_root / ".backstory" / "knowledge").is_dir())
        self.assertTrue((self.repo_root / ".backstory" / "knowledge" / "sessions").is_dir())
        self.assertTrue((self.repo_root / ".backstory" / "redactions").is_dir())

    def test_init_writes_config(self):
        result = initialize_repo(self.repo_root)

        self.assertTrue(result["config_written"])
        self.assertTrue((self.repo_root / ".backstory" / "config.json").exists())

    def test_init_installs_hooks(self):
        result = initialize_repo(self.repo_root, install_git_hooks=True)

        self.assertTrue(result["hooks_installed"])
        status = hooks_installed(self.repo_root)
        self.assertTrue(status["pre-commit"])
        self.assertTrue(status["post-commit"])

    def test_init_skips_hooks_when_requested(self):
        result = initialize_repo(self.repo_root, install_git_hooks=False)

        # Still reports current hook state (none)
        self.assertFalse(result["hooks_installed"])

    def test_init_config_preserved_without_force(self):
        # First init
        initialize_repo(self.repo_root)

        # Modify config
        cfg = self.repo_root / ".backstory" / "config.json"
        original_content = cfg.read_text()

        # Second init without force — should not overwrite
        result = initialize_repo(self.repo_root, force=False)
        self.assertFalse(result["config_written"])
        self.assertEqual(cfg.read_text(), original_content)

    def test_init_config_overwritten_with_force(self):
        initialize_repo(self.repo_root)

        result = initialize_repo(self.repo_root, force=True)
        self.assertTrue(result["config_written"])

    def test_print_init_summary_runs_without_error(self):
        result = initialize_repo(self.repo_root)
        # Should not raise
        import io
        import sys
        captured = io.StringIO()
        sys.stdout = captured
        try:
            print_init_summary(self.repo_root, result)
        finally:
            sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn("backstory initialized", output)
        self.assertIn("pre-commit", output)
        self.assertIn("post-commit", output)


if __name__ == "__main__":
    unittest.main()
