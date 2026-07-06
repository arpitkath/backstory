import json
import tempfile
import unittest
from pathlib import Path

from backstory.config import DEFAULT_CONFIG, config_path, load_config, write_default_config


class ConfigTestCase(unittest.TestCase):
    def test_default_config_matches_expected_shape(self):
        self.assertEqual(
            DEFAULT_CONFIG,
            {
                "version": 1,
                "storage": {
                    "root": ".backstory",
                    "knowledge_dir": "knowledge",
                    "sessions_dir": "sessions",
                    "pending_file": "latest.md",
                    "redactions_dir": "redactions",
                    "index_db": "index.sqlite",
                },
                "capture": {
                    "store_git_diff": True,
                    "store_transcripts": True,
                },
                "redaction": {
                    "enabled": True,
                },
            },
        )

    def test_write_and_load_default_config_in_repo_storage_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            written_path = write_default_config(repo_root)

            self.assertEqual(written_path, config_path(repo_root))
            self.assertEqual(written_path, repo_root / ".backstory" / "config.json")
            self.assertTrue(written_path.exists())
            self.assertEqual(load_config(repo_root), DEFAULT_CONFIG)
            self.assertEqual(json.loads(written_path.read_text()), DEFAULT_CONFIG)


if __name__ == "__main__":
    unittest.main()
