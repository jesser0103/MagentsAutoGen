"""Integration tests for ChromaRuleStore and ChromaPolicyIngestor.

These tests require chromadb. They use a deterministic local embedding function
so they do not download a model or require network access.

Run with:
    python -m pytest tests/test_chroma_store.py -v
"""

from __future__ import annotations

import gc
import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path


def _chroma_ready() -> bool:
    try:
        import chromadb  # noqa: F401

        return True
    except ImportError:
        return False


def _safe_tempdir(prefix: str) -> tempfile.TemporaryDirectory[str]:
    """Helper to create a TemporaryDirectory that ignores file lock errors on cleanup (Windows)."""
    return tempfile.TemporaryDirectory(prefix=prefix, ignore_cleanup_errors=True)


class DeterministicEmbeddingFunction:
    """Small, offline embedding function for hermetic ChromaDB tests."""

    dimensions = 64

    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors = []
        for document in input:
            vector = [0.0] * self.dimensions
            for term in re.findall(r"[a-zA-Z_]{3,}", document.lower()):
                digest = hashlib.sha256(term.encode("utf-8")).digest()
                vector[int.from_bytes(digest[:2], "big") % self.dimensions] += 1.0
            vectors.append(vector)
        return vectors


@unittest.skipUnless(_chroma_ready(), "chromadb not installed")
class ChromaRuleStoreTests(unittest.TestCase):
    """Verify semantic retrieval using a local ChromaDB collection."""

    def setUp(self) -> None:
        from src.rag.vector_store import ChromaRuleStore, PolicyRule

        self._tmpdir = _safe_tempdir("chroma-test-")
        self._embedding_function = DeterministicEmbeddingFunction()
        self._store = ChromaRuleStore(
            chroma_path=Path(self._tmpdir.name),
            relevance_threshold=0.3,
            embedding_function=self._embedding_function,
        )
        # Seed with two contrasting rules
        self._store.upsert_rules(
            (
                PolicyRule(
                    rule_id="SEC-001",
                    content=(
                        "SEC-001 Public Azure access is denied\n"
                        "Do not create public SSH, RDP, storage, or blob access. "
                        "Use private networking or an approved restricted network rule."
                    ),
                    source="data/internal_rules.txt",
                    source_hash="abc123",
                ),
                PolicyRule(
                    rule_id="GOV-001",
                    content=(
                        "GOV-001 Required resource tags\n"
                        "Every Azure resource must include environment, owner, and "
                        "cost_center tags."
                    ),
                    source="data/internal_rules.txt",
                    source_hash="abc123",
                ),
            )
        )

    def tearDown(self) -> None:
        if hasattr(self, "_store"):
            self._store.close()
            del self._store
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except Exception:
            shutil.rmtree(self._tmpdir.name, ignore_errors=True)

    def test_count_reflects_upserted_rules(self) -> None:
        self.assertEqual(self._store.count, 2)

    def test_security_query_returns_security_rule_above_threshold(self) -> None:
        """A query about public access should surface SEC-001, not GOV-001."""
        results = self._store.search("create storage account with public blob access", limit=1)
        self.assertTrue(results, "Expected at least one result above threshold")
        self.assertEqual(results[0].rule.rule_id, "SEC-001")
        self.assertGreater(results[0].score, 0.3)

    def test_retrieve_returns_content_strings_only(self) -> None:
        contents = self._store.retrieve("networking public storage", limit=2)
        self.assertIsInstance(contents, tuple)
        self.assertTrue(all(isinstance(c, str) for c in contents))

    def test_below_threshold_returns_empty(self) -> None:
        from src.rag.vector_store import ChromaRuleStore

        strict_store = ChromaRuleStore(
            chroma_path=Path(self._tmpdir.name),
            relevance_threshold=0.99,  # impossibly high
            embedding_function=self._embedding_function,
        )
        results = strict_store.search("public blob access", limit=4)
        strict_store.close()
        self.assertEqual(results, ())

    def test_delete_and_re_upsert_clears_old_documents(self) -> None:
        from src.rag.vector_store import PolicyRule

        self._store.delete_collection()
        self.assertEqual(self._store.count, 0)

        self._store.upsert_rules(
            (
                PolicyRule(
                    rule_id="NEW-001",
                    content="NEW-001 Fresh rule\nThis rule was added after deletion.",
                    source="test",
                    source_hash="xyz",
                ),
            )
        )
        self.assertEqual(self._store.count, 1)


@unittest.skipUnless(_chroma_ready(), "chromadb not installed")
class ChromaPolicyIngestorTests(unittest.TestCase):
    """Verify end-to-end ingestion via ChromaPolicyIngestor."""

    def test_ingest_writes_manifest_and_upserts_to_chroma(self) -> None:
        from src.rag.ingestion import ChromaPolicyIngestor

        with _safe_tempdir("chroma-ingest-") as tmpdir:
            root = Path(tmpdir)
            source = root / "rules.md"
            manifest = root / "policy_manifest.json"
            chroma_dir = root / "chroma"

            source.write_text(
                "# Smartovate rules\n\n"
                "## SEC-001 Public access denied\n"
                "Never expose public SSH or storage endpoints.\n\n"
                "## GOV-001 Required tags\n"
                "All resources must have environment, owner, and cost_center tags.\n",
                encoding="utf-8",
            )

            result = ChromaPolicyIngestor(
                chroma_path=chroma_dir,
                embedding_function=DeterministicEmbeddingFunction(),
            ).ingest(
                (source,), manifest
            )

            self.assertTrue(manifest.exists(), "Manifest file must be created")
            self.assertEqual(result.source_count, 1)
            self.assertEqual(result.chunk_count, 2)
            self.assertEqual(result.chroma_upserted, 2)
            gc.collect()

    def test_new_cost_center_rule_is_retrievable_after_ingest(self) -> None:
        """Adding a cost_center rule then re-ingesting makes it retrievable (E2E-03)."""
        from src.rag.ingestion import ChromaPolicyIngestor

        with _safe_tempdir("chroma-e2e-") as tmpdir:
            root = Path(tmpdir)
            source = root / "rules.md"
            manifest = root / "manifest.json"
            chroma_dir = root / "chroma"

            # First ingest — no cost_center rule
            source.write_text(
                "## SEC-001 Public access denied\nNo public networking.\n",
                encoding="utf-8",
            )
            ChromaPolicyIngestor(
                chroma_path=chroma_dir,
                embedding_function=DeterministicEmbeddingFunction(),
            ).ingest((source,), manifest)

            # Second ingest — add cost_center rule
            source.write_text(
                "## SEC-001 Public access denied\nNo public networking.\n\n"
                "## GOV-002 Cost center tagging\n"
                "Every resource must carry a cost_center tag for FinOps reporting.\n",
                encoding="utf-8",
            )
            ChromaPolicyIngestor(
                chroma_path=chroma_dir,
                embedding_function=DeterministicEmbeddingFunction(),
            ).ingest((source,), manifest)

            from src.rag.vector_store import ChromaRuleStore

            store = ChromaRuleStore(
                chroma_path=chroma_dir,
                relevance_threshold=0.2,
                embedding_function=DeterministicEmbeddingFunction(),
            )
            results = store.retrieve("deploy resource with cost center tagging", limit=4)
            store.close()

            self.assertTrue(
                any("cost_center" in r or "GOV-002" in r for r in results),
                msg=f"Expected cost_center rule to be retrievable after re-ingest. Got: {results}",
            )
            gc.collect()
