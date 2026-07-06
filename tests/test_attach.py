import subprocess
import tempfile
import unittest
from pathlib import Path

from backstory.attach import _get_commit_message, _render_summary
from backstory.dump import capture_session, save_pending_session
from backstory.attach import attach_pending_to_commit


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


def create_commit(path: Path, msg: str = "Initial commit") -> str:
    readme = path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=path, check=True, capture_output=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


class AttachTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)
        self.commit_hash = create_commit(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_attach_pending_to_commit_returns_session(self):
        session = capture_session(self.repo_root, task="Fix bug")
        save_pending_session(self.repo_root, session)

        result = attach_pending_to_commit(self.repo_root, self.commit_hash)
        self.assertIsNotNone(result)
        self.assertEqual(result["commit"]["hash"], self.commit_hash)  # type: ignore
        self.assertEqual(result["commit"]["message"], "Initial commit")  # type: ignore

    def test_attach_clears_pending(self):
        session = capture_session(self.repo_root)
        save_pending_session(self.repo_root, session)

        attach_pending_to_commit(self.repo_root, self.commit_hash)

        from backstory.dump import load_pending_session
        self.assertIsNone(load_pending_session(self.repo_root))

    def test_attach_returns_none_when_no_pending(self):
        result = attach_pending_to_commit(self.repo_root, self.commit_hash)
        self.assertIsNone(result)

    def test_get_commit_message(self):
        msg = _get_commit_message(self.repo_root, self.commit_hash)
        self.assertEqual(msg, "Initial commit")

    def test_render_summary_includes_commit_hash(self):
        session = capture_session(self.repo_root, task="Refactor")
        output = _render_summary(session, self.commit_hash, "Refactor")
        self.assertIn(self.commit_hash, output)
        self.assertIn("Refactor", output)
        self.assertIn("backstory", output)

    def test_render_summary_with_decisions(self):
        session = capture_session(self.repo_root, task="Fix bug")
        session["reasoning_summary"]["decisions"] = ["Use async", "Add retry"]
        output = _render_summary(session, self.commit_hash, "Fix bug")
        self.assertIn("Use async", output)
        self.assertIn("Add retry", output)

    def test_render_summary_with_risks(self):
        session = capture_session(self.repo_root, task="Deploy")
        session["reasoning_summary"]["risks"] = ["Rollback needed"]
        output = _render_summary(session, self.commit_hash, "Deploy")
        self.assertIn("Rollback needed", output)


if __name__ == "__main__":
    unittest.main()
