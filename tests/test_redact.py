import json
import tempfile
import unittest
from pathlib import Path

from backstory.redact import (
    SecretFinding,
    append_tombstone,
    load_tombstones,
    redact_session,
    scan_session,
    scan_text,
)


class ScanSessionTestCase(unittest.TestCase):
    """Tests for scan_session()."""

    def setUp(self):
        self.basic_session = {
            "session_id": "sha256:test123",
            "task": {
                "title": "Add login page",
                "user_prompt": "Implement a login page with OAuth",
            },
            "reasoning_summary": {
                "why": "Need authentication",
                "decisions": ["Use session-based auth"],
                "risks": ["None"],
                "followups": ["Add tests"],
                "alternatives": ["Could use JWT instead"],
            },
            "diff": {"staged": "diff --git a/app.py b/app.py", "unstaged": ""},
            "files": {"changed": ["app.py", "auth.py"]},
        }

    def test_session_with_no_secrets_returns_empty_list(self):
        findings = scan_session(self.basic_session)
        self.assertEqual(findings, [])

    def test_aws_key_in_task_title_finds_aws_access_key(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        session["task"]["title"] = "Fix AWS connection with AKIA1234567890123456"

        findings = scan_session(session)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "AWS Access Key")
        self.assertEqual(findings[0].confidence, 0.95)
        self.assertEqual(findings[0].context, "task.title")
        self.assertEqual(findings[0].value_snippet, "AKIA1234567890123456")

    def test_private_key_in_diff_finds_private_key(self):
        session = dict(self.basic_session)
        session["diff"] = dict(session["diff"])
        session["diff"]["staged"] = (
            "diff --git a/key.pem b/key.pem\n"
            "+-----BEGIN RSA PRIVATE KEY-----\n"
            "+MIIEpAIBAAKCAQEA..."
        )

        findings = scan_session(session)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "Private Key")
        self.assertEqual(findings[0].confidence, 0.99)
        self.assertEqual(findings[0].context, "diff.staged")

    def test_database_url_in_decisions_finds_database_url(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["decisions"] = [
            "Use postgres://db.example.com:5432/prod"
        ]

        findings = scan_session(session)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "Database URL")
        self.assertEqual(findings[0].confidence, 0.85)
        self.assertEqual(findings[0].context, "reasoning_summary.decisions[0]")

    def test_multiple_secrets_sorted_by_confidence_desc(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        session["task"]["title"] = (
            "Fix: postgres://user:pass@host/db and AKIA1234567890123456"
        )

        findings = scan_session(session)

        self.assertGreaterEqual(len(findings), 2)
        # Highest confidence first
        for i in range(len(findings) - 1):
            self.assertGreaterEqual(
                findings[i].confidence,
                findings[i + 1].confidence,
                msg=f"Findings not sorted: {findings[i].confidence} < {findings[i+1].confidence}",
            )

    def test_multiple_secrets_returns_all_findings(self):
        session = dict(self.basic_session)
        session["diff"] = dict(session["diff"])
        session["diff"]["unstaged"] = (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEA...\n"
        )
        session["task"] = dict(session["task"])
        session["task"]["title"] = "Use key AKIA1234567890123456"

        findings = scan_session(session)

        pattern_names = {f.pattern_name for f in findings}
        self.assertIn("Private Key", pattern_names)
        self.assertIn("AWS Access Key", pattern_names)

    def test_none_fields_do_not_crash(self):
        session = {
            "session_id": "sha256:test456",
            "task": None,
            "reasoning_summary": None,
            "diff": None,
            "files": None,
        }
        findings = scan_session(session)
        self.assertEqual(findings, [])

    def test_missing_fields_do_not_crash(self):
        session = {"session_id": "sha256:test789"}
        findings = scan_session(session)
        self.assertEqual(findings, [])

    def test_empty_task_does_not_crash(self):
        session = {
            "session_id": "sha256:empty",
            "task": {},
            "reasoning_summary": {},
            "diff": {},
            "files": {},
        }
        findings = scan_session(session)
        self.assertEqual(findings, [])

    def test_task_user_prompt_is_scanned(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        session["task"]["user_prompt"] = "I used the key AKIA1234567890123456"

        findings = scan_session(session)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].context, "task.user_prompt")

    def test_reasoning_summary_why_is_scanned(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["why"] = (
            "Because of AKIA1234567890123456 we fixed it"
        )

        findings = scan_session(session)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].context, "reasoning_summary.why")

    def test_reasoning_summary_risks_is_scanned(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["risks"] = [
            "postgres://user:pass@host/db exposed"
        ]

        findings = scan_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertIn("reasoning_summary.risks", findings[0].context)

    def test_reasoning_summary_followups_is_scanned(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["followups"] = [
            "Rotate AKIA1234567890123456"
        ]

        findings = scan_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertIn("reasoning_summary.followups", findings[0].context)

    def test_reasoning_summary_alternatives_is_scanned(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["alternatives"] = [
            "Use key AKIA1234567890123456 instead"
        ]

        findings = scan_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertIn("reasoning_summary.alternatives", findings[0].context)

    def test_diff_unstaged_is_scanned(self):
        session = dict(self.basic_session)
        session["diff"] = dict(session["diff"])
        session["diff"]["unstaged"] = "bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dR1fVvf7TQ"

        findings = scan_session(session)

        pattern_names = {f.pattern_name for f in findings}
        contexts = {f.context for f in findings}
        self.assertIn("Bearer Token", pattern_names)
        self.assertIn("diff.unstaged", contexts)

    def test_files_changed_are_not_scanned_for_secrets_by_default(self):
        # files.changed paths are scanned for patterns; they typically won't match
        session = dict(self.basic_session)
        session["files"] = {"changed": ["src/main.py", "src/utils.py"]}

        findings = scan_session(session)
        # file paths like "src/main.py" should not match any pattern
        self.assertEqual(findings, [])

    def test_files_changed_with_secret_path(self):
        # If a file path happens to contain a secret pattern
        session = dict(self.basic_session)
        session["files"] = {"changed": ["backup_AKIA1234567890123456.txt"]}

        findings = scan_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "AWS Access Key")


class ScanTextTestCase(unittest.TestCase):
    """Tests for scan_text()."""

    def test_empty_string_returns_empty_list(self):
        findings = scan_text("", "test.context")
        self.assertEqual(findings, [])

    def test_no_patterns_matched_returns_empty_list(self):
        findings = scan_text("Hello world, this is harmless text.", "test.context")
        self.assertEqual(findings, [])

    def test_known_pattern_matched_returns_correct_finding(self):
        findings = scan_text("My key is AKIA1234567890123456", "task.title")

        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.pattern_name, "AWS Access Key")
        self.assertEqual(f.value_snippet, "AKIA1234567890123456")
        self.assertEqual(f.context, "task.title")
        self.assertEqual(f.confidence, 0.95)

    def test_multiple_matches_in_same_text(self):
        text = (
            "Key1: AKIA1111111111111111, Key2: AKIA2222222222222222"
        )
        findings = scan_text(text, "task.title")

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].pattern_name, "AWS Access Key")
        self.assertEqual(findings[1].pattern_name, "AWS Access Key")

    def test_snippet_truncated_to_20_chars(self):
        findings = scan_text("AKIA12345678901234567890", "test")
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(findings[0].value_snippet), 20)

    def test_github_token_is_detected(self):
        findings = scan_text("ghp_abcdefghijklmnopqrstuvwxyz1234567890", "test")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "GitHub Token")

    def test_bearer_token_is_detected(self):
        findings = scan_text("bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dGVzdGVzdA.test", "test")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "Bearer Token")

    def test_slack_token_is_detected(self):
        findings = scan_text("xoxb-1234567890-abcdefghij", "test")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "Slack Token")

    def test_jwt_token_is_detected(self):
        findings = scan_text(
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dGVzdGVzdGVzdA",
            "test",
        )
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "JWT Token")

    def test_password_in_url_is_detected(self):
        findings = scan_text("http://user:pass123@example.com", "test")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "Password in URL")

    def test_github_old_token_is_detected(self):
        findings = scan_text("gh_abcdefabcdefabcdefabcd1234", "test")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "GitHub Old Token")

    def test_api_key_generic_is_detected(self):
        findings = scan_text("api_key=abcdefghijklmnopqrstuvwxyz123456", "test")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "API Key (generic)")


class RedactSessionTestCase(unittest.TestCase):
    """Tests for redact_session()."""

    def setUp(self):
        self.basic_session = {
            "session_id": "sha256:test123",
            "task": {
                "title": "Add login page",
                "user_prompt": "Implement a login page",
            },
            "reasoning_summary": {
                "why": "Need authentication",
                "decisions": ["Use session-based auth"],
                "risks": [],
                "followups": [],
                "alternatives": [],
            },
            "diff": {"staged": "", "unstaged": ""},
            "files": {"changed": ["app.py"]},
        }

    def test_session_with_no_secrets_returns_identical_copy(self):
        redacted, findings = redact_session(self.basic_session)

        self.assertEqual(findings, [])
        self.assertEqual(redacted["session_id"], self.basic_session["session_id"])
        self.assertEqual(redacted["task"]["title"], self.basic_session["task"]["title"])
        self.assertEqual(
            redacted["reasoning_summary"]["decisions"],
            self.basic_session["reasoning_summary"]["decisions"],
        )

    def test_session_with_aws_key_redacts_it(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        session["task"]["title"] = "Fix AWS connection with AKIA1234567890123456"

        redacted, findings = redact_session(session)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "AWS Access Key")
        self.assertEqual(
            redacted["task"]["title"],
            "Fix AWS connection with [REDACTED:AWS Access Key]",
        )

    def test_original_session_is_not_mutated(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        original_title = session["task"]["title"]
        session["task"]["title"] = "Key is AKIA1234567890123456"

        redacted, _ = redact_session(session)

        # Original should still have the key
        self.assertIn("AKIA1234567890123456", session["task"]["title"])
        # Redacted should not
        self.assertNotIn("AKIA1234567890123456", redacted["task"]["title"])
        self.assertIn("[REDACTED:AWS Access Key]", redacted["task"]["title"])

    def test_multiple_patterns_in_same_field_all_redacted(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        session["task"]["title"] = (
            "Keys: AKIA1111111111111111 and AKIA2222222222222222"
        )

        redacted, findings = redact_session(session)

        self.assertEqual(len(findings), 2)
        self.assertEqual(
            redacted["task"]["title"],
            "Keys: [REDACTED:AWS Access Key] and [REDACTED:AWS Access Key]",
        )

    def test_private_key_in_diff_redacted(self):
        session = dict(self.basic_session)
        session["diff"] = dict(session["diff"])
        session["diff"]["staged"] = (
            "diff --git a/key.pem b/key.pem\n"
            "+-----BEGIN RSA PRIVATE KEY-----\n"
            "+MIIEpAIBAAKCAQEA..."
        )

        redacted, findings = redact_session(session)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "Private Key")
        self.assertIn("[REDACTED:Private Key]", redacted["diff"]["staged"])

    def test_database_url_in_decisions_redacted(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["decisions"] = [
            "Use postgres://db.example.com:5432/prod"
        ]

        redacted, findings = redact_session(session)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern_name, "Database URL")
        self.assertIn("[REDACTED:Database URL]", redacted["reasoning_summary"]["decisions"][0])

    def test_user_prompt_redacted(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        session["task"]["user_prompt"] = "Use key AKIA1234567890123456 to connect"

        redacted, findings = redact_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertIn("[REDACTED:AWS Access Key]", redacted["task"]["user_prompt"])
        self.assertNotIn("AKIA1234567890123456", redacted["task"]["user_prompt"])

    def test_reasoning_summary_why_redacted(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["why"] = "Key AKIA1234567890123456 was exposed"

        redacted, findings = redact_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertIn("[REDACTED:AWS Access Key]", redacted["reasoning_summary"]["why"])
        self.assertNotIn("AKIA1234567890123456", redacted["reasoning_summary"]["why"])

    def test_risks_redacted(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["risks"] = [
            "postgres://user:pass@host/db leaked"
        ]

        redacted, findings = redact_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertIn("[REDACTED:Database URL]", redacted["reasoning_summary"]["risks"][0])

    def test_followups_redacted(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["followups"] = [
            "Rotate AKIA1234567890123456"
        ]

        redacted, findings = redact_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertIn(
            "[REDACTED:AWS Access Key]",
            redacted["reasoning_summary"]["followups"][0],
        )

    def test_alternatives_redacted(self):
        session = dict(self.basic_session)
        session["reasoning_summary"] = dict(session["reasoning_summary"])
        session["reasoning_summary"]["alternatives"] = [
            "Use AKIA1234567890123456 instead"
        ]

        redacted, findings = redact_session(session)

        self.assertGreaterEqual(len(findings), 1)
        self.assertIn(
            "[REDACTED:AWS Access Key]",
            redacted["reasoning_summary"]["alternatives"][0],
        )

    def test_diff_unstaged_redacted(self):
        session = dict(self.basic_session)
        session["diff"] = dict(session["diff"])
        session["diff"]["unstaged"] = "bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dGVzdA"

        redacted, findings = redact_session(session)

        bearer_findings = [f for f in findings if f.pattern_name == "Bearer Token"]
        self.assertGreaterEqual(len(bearer_findings), 1)
        self.assertIn("[REDACTED:Bearer Token]", redacted["diff"]["unstaged"])

    def test_multiple_different_patterns_in_same_field(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        session["task"]["title"] = (
            "postgres://user:pass@host/db and AKIA1234567890123456"
        )

        redacted, findings = redact_session(session)

        self.assertGreaterEqual(len(findings), 2)
        self.assertIn("[REDACTED:Database URL]", redacted["task"]["title"])
        self.assertIn("[REDACTED:AWS Access Key]", redacted["task"]["title"])

    def test_redact_returns_findings_sorted_by_confidence(self):
        session = dict(self.basic_session)
        session["task"] = dict(session["task"])
        # Contains both a Private Key (0.99) and an AWS Access Key (0.95)
        session["diff"] = dict(session["diff"])
        session["diff"]["staged"] = "-----BEGIN PRIVATE KEY-----"
        session["task"]["title"] = "AKIA1234567890123456"

        _, findings = redact_session(session)

        self.assertGreaterEqual(len(findings), 2)
        self.assertEqual(findings[0].pattern_name, "Private Key")
        self.assertEqual(findings[1].pattern_name, "AWS Access Key")


class AppendLoadTombstoneTestCase(unittest.TestCase):
    """Tests for append_tombstone() and load_tombstones()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        # Ensure the .backstory/redactions directory and parent structure exists
        # append_tombstone calls ensure_storage_layout which creates the full layout
        # But we need a git repo for that to work
        import subprocess

        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_append_then_load_returns_entry(self):
        append_tombstone(
            self.repo_root,
            old_session_id="sha256:abc123",
            new_session_id="sha256:def456",
        )

        entries = load_tombstones(self.repo_root)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["old"], "sha256:abc123")
        self.assertEqual(entries[0]["new"], "sha256:def456")
        self.assertEqual(entries[0]["reason"], "redacted")
        self.assertIn("timestamp", entries[0])

    def test_no_tombstones_file_returns_empty_list(self):
        entries = load_tombstones(self.repo_root)
        self.assertEqual(entries, [])

    def test_multiple_entries_returns_all(self):
        append_tombstone(self.repo_root, "sha256:old1", "sha256:new1")
        append_tombstone(self.repo_root, "sha256:old2", "sha256:new2")
        append_tombstone(self.repo_root, "sha256:old3", "sha256:new3")

        entries = load_tombstones(self.repo_root)

        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["old"], "sha256:old1")
        self.assertEqual(entries[1]["old"], "sha256:old2")
        self.assertEqual(entries[2]["old"], "sha256:old3")

    def test_entry_has_all_expected_keys(self):
        append_tombstone(self.repo_root, "sha256:old", "sha256:new")

        entries = load_tombstones(self.repo_root)

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertIn("old", entry)
        self.assertIn("new", entry)
        self.assertIn("timestamp", entry)
        self.assertIn("reason", entry)

    def test_append_multiple_then_load_preserves_insertion_order(self):
        ids = [f"sha256:old{i}" for i in range(5)]
        for i, old_id in enumerate(ids):
            append_tombstone(self.repo_root, old_id, f"sha256:new{i}")

        entries = load_tombstones(self.repo_root)

        self.assertEqual(len(entries), 5)
        for i, entry in enumerate(entries):
            self.assertEqual(entry["old"], f"sha256:old{i}")
            self.assertEqual(entry["new"], f"sha256:new{i}")

    def test_append_tombstone_does_not_raise_on_nonexistent_repo_root(self):
        """append_tombstone raises when the repo_root doesn't exist."""
        import tempfile as _tf
        valid_parent = Path(_tf.mkdtemp())
        non_repo = valid_parent / "does_not_exist_yet"
        # ensure_storage_layout will try to create .backstory under a
        # non-existent dir -> FileNotFoundError -> propagates from
        # append_tombstone because ensure_storage_layout is not
        # wrapped in the OSError try/except.
        with self.assertRaises(FileNotFoundError):
            append_tombstone(non_repo, "sha256:old", "sha256:new")


if __name__ == "__main__":
    unittest.main()
