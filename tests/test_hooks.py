import os
import stat
import tempfile
import unittest
from pathlib import Path

from backstory.hooks import (
    PRE_COMMIT_CONTENT,
    POST_COMMIT_CONTENT,
    hooks_dir,
    hooks_installed,
    install_hooks,
    uninstall_hooks,
)


class HooksTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        (self.repo_root / ".git").mkdir(parents=True)
        (self.repo_root / ".git" / "hooks").mkdir(parents=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_hooks_dir_returns_git_hooks_path(self):
        self.assertEqual(hooks_dir(self.repo_root), self.repo_root / ".git" / "hooks")

    def test_install_hooks_creates_both_scripts(self):
        written = install_hooks(self.repo_root)

        self.assertEqual(len(written), 2)

        pre = self.repo_root / ".git" / "hooks" / "pre-commit"
        post = self.repo_root / ".git" / "hooks" / "post-commit"

        self.assertTrue(pre.exists())
        self.assertTrue(post.exists())

        # Check content contains backstory marker
        self.assertIn("backstory", pre.read_text())
        self.assertIn("backstory", post.read_text())

    def test_install_hooks_makes_scripts_executable(self):
        install_hooks(self.repo_root)

        pre = self.repo_root / ".git" / "hooks" / "pre-commit"
        st = os.stat(pre)
        self.assertTrue(st.st_mode & stat.S_IXUSR)
        self.assertTrue(st.st_mode & stat.S_IXGRP)
        self.assertTrue(st.st_mode & stat.S_IXOTH)

    def test_hooks_installed_returns_true_when_installed(self):
        install_hooks(self.repo_root)

        status = hooks_installed(self.repo_root)
        self.assertTrue(status["pre-commit"])
        self.assertTrue(status["post-commit"])

    def test_hooks_installed_returns_false_when_not_installed(self):
        status = hooks_installed(self.repo_root)
        self.assertFalse(status["pre-commit"])
        self.assertFalse(status["post-commit"])

    def test_uninstall_hooks_removes_backstory_hooks(self):
        install_hooks(self.repo_root)

        removed = uninstall_hooks(self.repo_root)
        self.assertEqual(removed, 2)

        self.assertFalse((self.repo_root / ".git" / "hooks" / "pre-commit").exists())
        self.assertFalse((self.repo_root / ".git" / "hooks" / "post-commit").exists())

    def test_uninstall_hooks_does_not_remove_other_hooks(self):
        pre = self.repo_root / ".git" / "hooks" / "pre-commit"
        pre.write_text("#!/bin/sh\necho custom\n")

        removed = uninstall_hooks(self.repo_root)
        self.assertEqual(removed, 0)
        self.assertTrue(pre.exists())

    def test_pre_commit_script_content(self):
        self.assertIn("dump --hook pre-commit", PRE_COMMIT_CONTENT)
        self.assertIn("#!/bin/sh", PRE_COMMIT_CONTENT)

    def test_post_commit_script_content(self):
        self.assertIn("attach HEAD --hook post-commit", POST_COMMIT_CONTENT)
        self.assertIn("#!/bin/sh", POST_COMMIT_CONTENT)


if __name__ == "__main__":
    unittest.main()
