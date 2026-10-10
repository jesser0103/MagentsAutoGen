"""Versioned local policy-ingestion support for the RAG boundary."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.rag.vector_store import ChromaRuleStore, LocalRuleStore, PolicyRule

log = logging.getLogger(__name__)

MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PolicyIngestionResult:
    """Non-secret summary emitted after a local policy-manifest refresh."""

    manifest_path: Path
    source_count: int
    chunk_count: int
    chroma_upserted: int = 0


class PolicyIngestor:
    """Convert approved policy files into a durable, hash-recorded manifest."""

    def ingest(
        self,
        source_paths: tuple[Path, ...],
        manifest_path: Path,
    ) -> PolicyIngestionResult:
        rules = []
        sources = []
        for source_path in source_paths:
            if not source_path.exists():
                raise FileNotFoundError(source_path)
            store = LocalRuleStore.from_markdown(source_path, relevance_threshold=0)
            source_rules = store.rules
            sources.append(_source_record(source_path, source_rules))
            rules.extend(source_rules)

        payload = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "chunk_strategy": "markdown_h2_sections",
            "sources": sources,
            "rules": [_rule_record(rule) for rule in rules],
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(manifest_path)
        return PolicyIngestionResult(
            manifest_path=manifest_path,
            source_count=len(source_paths),
            chunk_count=len(rules),
        )


class ChromaPolicyIngestor:
    """Ingest policy rules into a ChromaDB collection for semantic retrieval.

    Writes the JSON manifest and then upserts all rules into a ChromaDB collection
    using the configured embedding function, normally Azure OpenAI.
    """

    def __init__(
        self,
        chroma_path: Path,
        relevance_threshold: float = 0.2,
        collection_name: str | None = None,
        embedding_function: object | None = None,
    ) -> None:
        self._chroma_path = chroma_path
        self._relevance_threshold = relevance_threshold
        self._collection_name = collection_name
        self._embedding_function = embedding_function

    def ingest(
        self,
        source_paths: tuple[Path, ...],
        manifest_path: Path,
    ) -> PolicyIngestionResult:
        # Step 1: build the JSON manifest (lexical ingestor)
        base_result = PolicyIngestor().ingest(source_paths, manifest_path)

        # Step 2: load rules back from the manifest
        rules = load_policy_manifest(manifest_path)
        if not rules:
            log.warning("No rules found in manifest — Chroma collection not updated.")
            return base_result

        # Step 3: upsert into ChromaDB
        store = ChromaRuleStore(
            chroma_path=self._chroma_path,
            relevance_threshold=self._relevance_threshold,
            collection_name=self._collection_name or "magent_policies",
            embedding_function=self._embedding_function,
        )
        store.upsert_rules(rules)
        log.info(
            "ChromaPolicyIngestor: %d rule(s) upserted to %s",
            len(rules),
            self._chroma_path,
        )

        return PolicyIngestionResult(
            manifest_path=base_result.manifest_path,
            source_count=base_result.source_count,
            chunk_count=base_result.chunk_count,
            chroma_upserted=len(rules),
        )


def load_policy_manifest(path: Path) -> tuple[PolicyRule, ...]:
    """Load a manifest written by PolicyIngestor without requiring Chroma or Azure."""
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unsupported policy-manifest schema version")
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError("Policy manifest rules must be a list")

    rules = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise ValueError("Policy manifest contains an invalid rule")
        rule_id = raw_rule.get("rule_id")
        content = raw_rule.get("content")
        source = raw_rule.get("source")
        source_hash = raw_rule.get("source_hash")
        values = (rule_id, content, source, source_hash)
        if not all(isinstance(value, str) and value for value in values):
            raise ValueError("Policy manifest contains an incomplete rule")
        rules.append(
            PolicyRule(
                rule_id=rule_id,
                content=content,
                source=source,
                source_hash=source_hash,
            )
        )
    return tuple(rules)


def _source_record(source_path: Path, rules: tuple[PolicyRule, ...]) -> dict[str, object]:
    source_hash = rules[0].source_hash if rules else ""
    return {
        "path": str(source_path),
        "sha256": source_hash,
        "chunk_count": len(rules),
    }


def _rule_record(rule: PolicyRule) -> dict[str, str]:
    return {
        "rule_id": rule.rule_id,
        "content": rule.content,
        "source": rule.source,
        "source_hash": rule.source_hash,
    }
