"""Tests for the immutable append-only audit log (Task 2.3)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import unittest

from src.utils.audit_log import AuditEntry, AuditLogger


class AuditEntryTests(unittest.TestCase):
    """Verify the hash-chain integrity of individual audit entries."""

    def test_entry_hash_is_deterministic(self) -> None:
        a = AuditEntry(
            action="test", user_id="u1", username="alice",
            auth_type="api_key", run_id="run-1", timestamp="2025-01-01T00:00:00+00:00",
        )
        b = AuditEntry(
            action="test", user_id="u1", username="alice",
            auth_type="api_key", run_id="run-1", timestamp="2025-01-01T00:00:00+00:00",
        )
        self.assertEqual(a.entry_hash, b.entry_hash)
        self.assertTrue(len(a.entry_hash) == 64)  # SHA-256 hex

    def test_different_actions_produce_different_hashes(self) -> None:
        a = AuditEntry(action="submit", user_id="u1", username="alice", auth_type="api_key", timestamp="t1")
        b = AuditEntry(action="approve", user_id="u1", username="alice", auth_type="api_key", timestamp="t1")
        self.assertNotEqual(a.entry_hash, b.entry_hash)

    def test_to_dict_includes_all_fields(self) -> None:
        entry = AuditEntry(
            action="plan_approved", user_id="u1", username="bob",
            auth_type="better_auth_jwt", run_id="run-42",
        )
        d = entry.to_dict()
        self.assertIn("action", d)
        self.assertIn("entry_hash", d)
        self.assertIn("prev_hash", d)
        self.assertEqual(d["action"], "plan_approved")


class AuditLoggerTests(unittest.TestCase):
    """Verify append-only file writing and hash-chain continuity."""

    def test_log_creates_file_and_writes_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(Path(tmpdir) / "test_audit.jsonl")
            logger.log("mission_submitted", "u1", "alice", "api_key", run_id="run-1", request_preview="Deploy AKS")

            log_path = Path(tmpdir) / "test_audit.jsonl"
            self.assertTrue(log_path.exists())
            lines = log_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)

            record = json.loads(lines[0])
            self.assertEqual(record["action"], "mission_submitted")
            self.assertEqual(record["username"], "alice")
            self.assertEqual(record["run_id"], "run-1")
            self.assertIn("entry_hash", record)

    def test_hash_chain_links_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(Path(tmpdir) / "chain.jsonl")
            logger.log("submit", "u1", "alice", "key", run_id="r1")
            logger.log("approve", "u1", "alice", "key", run_id="r1")
            logger.log("reject", "u2", "bob", "jwt", run_id="r2", feedback="needs changes")

            lines = (Path(tmpdir) / "chain.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(lines), 3)

            records = [json.loads(line) for line in lines]
            # First entry has empty prev_hash
            self.assertEqual(records[0]["prev_hash"], "")
            # Each subsequent entry's prev_hash == previous entry's entry_hash
            self.assertEqual(records[1]["prev_hash"], records[0]["entry_hash"])
            self.assertEqual(records[2]["prev_hash"], records[1]["entry_hash"])

    def test_resumed_logger_continues_hash_chain(self) -> None:
        """A new AuditLogger instance reading an existing file should continue the chain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "resume.jsonl"
            logger1 = AuditLogger(path)
            logger1.log("submit", "u1", "alice", "key", run_id="r1")

            # Create a second logger reading from the same file
            logger2 = AuditLogger(path)
            logger2.log("approve", "u1", "alice", "key", run_id="r1")

            lines = path.read_text().strip().splitlines()
            records = [json.loads(line) for line in lines]
            self.assertEqual(len(records), 2)
            # Chain must be intact even across logger instances
            self.assertEqual(records[1]["prev_hash"], records[0]["entry_hash"])

    def test_detail_fields_are_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(Path(tmpdir) / "trunc.jsonl")
            long_text = "A" * 500
            logger.log("submit", "u1", "alice", "key", request_preview=long_text)

            line = (Path(tmpdir) / "trunc.jsonl").read_text().strip()
            record = json.loads(line)
            self.assertLessEqual(len(record["detail"]["request_preview"]), 120)

    def test_convenience_methods_write_correct_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(Path(tmpdir) / "conv.jsonl")
            logger.mission_submitted("u1", "alice", "key", "r1", "Deploy AKS")
            logger.plan_approved("u1", "alice", "key", "r1")
            logger.plan_rejected("u2", "bob", "jwt", "r2", "Needs Azure auth")
            logger.mission_deleted("u1", "alice", "key", "r1")
            logger.auth_failure("invalid_api_key", ip="10.0.0.1")

            lines = (Path(tmpdir) / "conv.jsonl").read_text().strip().splitlines()
            actions = [json.loads(line)["action"] for line in lines]
            self.assertEqual(actions, [
                "mission_submitted",
                "plan_approved",
                "plan_rejected",
                "mission_deleted",
                "auth_failure",
            ])


if __name__ == "__main__":
    unittest.main()
