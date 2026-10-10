import tempfile
import unittest
from pathlib import Path

from src.rag.ingestion import PolicyIngestor, load_policy_manifest
from src.rag.vector_store import LocalRuleStore, PolicyRule


class PolicyIngestionTests(unittest.TestCase):
    def test_ingestion_records_rules_and_source_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "rules.md"
            manifest = root / "policy_manifest.json"
            source.write_text(
                "# Approved rules\n\n"
                "## GOV-001 Required tags\n"
                "Every resource must include environment, owner, and cost_center tags.\n",
                encoding="utf-8",
            )

            result = PolicyIngestor().ingest((source,), manifest)
            rules = load_policy_manifest(manifest)

        self.assertEqual(result.source_count, 1)
        self.assertEqual(result.chunk_count, 1)
        self.assertEqual(rules[0].rule_id, "GOV-001")
        self.assertEqual(len(rules[0].source_hash), 64)

    def test_reingestion_replaces_changed_policy_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "rules.md"
            manifest = root / "policy_manifest.json"
            source.write_text(
                "## GOV-001 Required tags\n"
                "Every resource must include environment and owner tags.\n",
                encoding="utf-8",
            )
            ingestor = PolicyIngestor()
            ingestor.ingest((source,), manifest)
            initial_rule = load_policy_manifest(manifest)[0]

            source.write_text(
                "## GOV-001 Required tags\n"
                "Every resource must include environment, owner, and cost_center tags.\n",
                encoding="utf-8",
            )
            ingestor.ingest((source,), manifest)
            refreshed_rule = load_policy_manifest(manifest)[0]

        self.assertNotEqual(initial_rule.source_hash, refreshed_rule.source_hash)
        self.assertIn("cost_center", refreshed_rule.content)


class LocalRuleStoreTests(unittest.TestCase):
    def test_threshold_excludes_weak_policy_matches(self) -> None:
        store = LocalRuleStore(
            (
                PolicyRule(
                    "SEC-001",
                    "Private storage access requires approved networking.",
                ),
            ),
            relevance_threshold=0.6,
        )

        matches = store.search("Create a storage account with unrelated logging", limit=4)

        self.assertEqual(matches, ())

    def test_search_returns_relevance_score_and_source_metadata(self) -> None:
        store = LocalRuleStore(
            (
                PolicyRule(
                    "GOV-001",
                    "Required Azure resource tags include environment owner cost_center.",
                    source="data/rules.md",
                    source_hash="abc123",
                ),
            ),
            relevance_threshold=0.2,
        )

        matches = store.search("Add cost_center tags to an Azure resource", limit=1)

        self.assertEqual(matches[0].rule.rule_id, "GOV-001")
        self.assertGreater(matches[0].score, 0)
        self.assertEqual(matches[0].rule.source_hash, "abc123")
