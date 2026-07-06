import argparse
import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from backstory.attach import attach_pending_to_commit
from backstory.cli import _handle_diff
from backstory.contradiction import detect_potential_contradictions
from backstory.dump import capture_session, save_pending_session
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


class ContradictionDetectionTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        init_repo(self.repo_root)
        self.commit_hash = create_commit(self.repo_root)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_detect_potential_contradictions_flags_prior_session_for_same_file(self):
        decisions = ExtractedDecisions(
            agent_name="claude-code",
            model="claude-sonnet",
            task="Fix billing webhook",
            decisions=["payment.failed should mark subscription as pending, not cancelled"],
            files_changed=["app/billing/webhook.py"],
        )
        session = capture_session(
            repo_root=self.repo_root,
            decisions=decisions,
        )
        save_pending_session(self.repo_root, session)
        attach_pending_to_commit(self.repo_root, self.commit_hash)

        warnings = detect_potential_contradictions(
            self.repo_root,
            ["app/billing/webhook.py"],
        )

        self.assertTrue(warnings)
        self.assertIn("payment.failed", warnings[0])
        self.assertIn(self.commit_hash[:7], warnings[0])

    def test_diff_command_displays_contradiction_warning(self):
        tracked_file = self.repo_root / "app" / "billing" / "webhook.py"
        tracked_file.parent.mkdir(parents=True, exist_ok=True)
        tracked_file.write_text("initial\n")
        subprocess.run(["git", "add", "app/billing/webhook.py"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add webhook"], cwd=self.repo_root, check=True, capture_output=True)

        decisions = ExtractedDecisions(
            agent_name="claude-code",
            model="claude-sonnet",
            task="Fix billing webhook",
            decisions=["payment.failed should mark subscription as pending, not cancelled"],
            files_changed=["app/billing/webhook.py"],
        )
        session = capture_session(
            repo_root=self.repo_root,
            decisions=decisions,
        )
        save_pending_session(self.repo_root, session)
        attach_pending_to_commit(self.repo_root, self.commit_hash)

        tracked_file.write_text("updated\n")

        buffer = io.StringIO()
        cwd = os.getcwd()
        try:
            os.chdir(self.repo_root)
            with redirect_stdout(buffer):
                result = _handle_diff(argparse.Namespace())
        finally:
            os.chdir(cwd)

        self.assertEqual(result, 0)
        output = buffer.getvalue()
        self.assertIn("Potential contradictions:", output)
        self.assertIn("payment.failed", output)


if __name__ == "__main__":
    unittest.main()
