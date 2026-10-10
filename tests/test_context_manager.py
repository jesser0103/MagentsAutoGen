import unittest

from src.utils.context_manager import BoundedContextManager


class BoundedContextManagerTests(unittest.TestCase):
    def test_long_context_keeps_boundaries_and_records_omission_hash(self) -> None:
        manager = BoundedContextManager(max_characters=300)
        request = "Start requirement. " + ("middle " * 100) + "Final requirement."

        snapshot = manager.prepare(request)

        self.assertTrue(snapshot.truncated)
        self.assertLessEqual(len(snapshot.content), 300)
        self.assertIn("Start requirement.", snapshot.content)
        self.assertIn("Final requirement.", snapshot.content)
        self.assertIn("omitted-content sha256=", snapshot.content)
        self.assertEqual(len(snapshot.omitted_sha256 or ""), 64)

    def test_short_context_is_preserved_without_audit_hash(self) -> None:
        snapshot = BoundedContextManager(max_characters=300).prepare("Create a private resource.")

        self.assertFalse(snapshot.truncated)
        self.assertEqual(snapshot.content, "Create a private resource.")
        self.assertIsNone(snapshot.omitted_sha256)
