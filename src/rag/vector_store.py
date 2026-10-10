"""Local, versioned policy retrieval with a ChromaDB-backed semantic store."""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from src.utils.retry import RetryExhaustedError, retry_sync

_RULE_HEADING = re.compile(r"^([A-Z][A-Z0-9_]*-\d+)\b")
_STOP_WORDS = {
    "add",
    "and",
    "azure",
    "code",
    "create",
    "for",
    "from",
    "into",
    "make",
    "that",
    "the",
    "this",
    "with",
}

log = logging.getLogger(__name__)

_CHROMA_COLLECTION = "magent_policies"


@dataclass(frozen=True)
class PolicyRule:
    """One independently retrievable internal-policy chunk."""

    rule_id: str
    content: str
    source: str = "unknown"
    source_hash: str = ""


@dataclass(frozen=True)
class RetrievedPolicy:
    """A policy rule selected with its deterministic relevance evidence."""

    rule: PolicyRule
    score: float


# ---------------------------------------------------------------------------
# Lexical store (no external dependencies, always available)
# ---------------------------------------------------------------------------


class LocalRuleStore:
    """Local lexical retrieval — used when ChromaDB is not configured."""

    def __init__(
        self,
        rules: tuple[PolicyRule, ...],
        relevance_threshold: float = 0.2,
    ) -> None:
        if not 0 <= relevance_threshold <= 1:
            raise ValueError("relevance_threshold must be between 0 and 1")
        self._rules = rules
        self._relevance_threshold = relevance_threshold

    @classmethod
    def from_markdown(
        cls,
        path: Path,
        relevance_threshold: float = 0.2,
    ) -> "LocalRuleStore":
        if not path.exists():
            return cls((), relevance_threshold)
        content = path.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return cls(
            _parse_rules(content, source_name=str(path), source_hash=source_hash),
            relevance_threshold,
        )

    @classmethod
    def from_manifest(
        cls,
        path: Path,
        relevance_threshold: float = 0.2,
    ) -> "LocalRuleStore":
        from src.rag.ingestion import load_policy_manifest

        return cls(load_policy_manifest(path), relevance_threshold)

    def retrieve(self, query: str, limit: int = 4) -> tuple[str, ...]:
        """Return only content above the configured relevance threshold."""
        return tuple(result.rule.content for result in self.search(query, limit))

    @property
    def rules(self) -> tuple[PolicyRule, ...]:
        """Expose immutable rules for local manifest generation and tests."""
        return self._rules

    def search(self, query: str, limit: int = 4) -> tuple[RetrievedPolicy, ...]:
        """Return scored policy evidence for audit logging and UI display."""
        if limit < 1:
            return ()
        query_terms = _terms(query)
        if not query_terms:
            return ()

        matches = []
        for rule in self._rules:
            overlap = query_terms & _terms(rule.content)
            score = len(overlap) / len(query_terms)
            if score >= self._relevance_threshold:
                matches.append(RetrievedPolicy(rule=rule, score=round(score, 4)))
        matches.sort(key=lambda result: (-result.score, result.rule.rule_id))
        return tuple(matches[:limit])


# ---------------------------------------------------------------------------
# Azure OpenAI embedding function for ChromaDB
# ---------------------------------------------------------------------------


class AzureOpenAIEmbeddingFunction:
    """ChromaDB-compatible embedding function using Azure OpenAI text-embedding models.

    Compatible with ``text-embedding-3-small`` (1536 dims) and
    ``text-embedding-3-large`` (3072 dims, better recall).

    Usage::

        ef = AzureOpenAIEmbeddingFunction(
            endpoint="https://<resource>.openai.azure.com/",
            api_key="<key>",
            deployment_name="magent-embeddings",
        )
        store = ChromaRuleStore(chroma_path, embedding_function=ef)

    The class satisfies the ChromaDB ``EmbeddingFunction`` protocol — any object
    that implements ``__call__(input: list[str]) -> list[list[float]]``.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment_name: str,
        api_version: str = "2024-02-01",
        client: object | None = None,
        retry_max_attempts: int = 2,
        retry_base_delay_seconds: float = 0.5,
        retry_max_delay_seconds: float = 5,
    ) -> None:
        if client is None:
            if _uses_openai_compatible_base_url(endpoint):
                from openai import OpenAI

                client = OpenAI(
                    base_url=_openai_compatible_base_url(endpoint),
                    api_key=api_key,
                )
            else:
                from openai import AzureOpenAI

                client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=api_key,
                    api_version=api_version,
                )
        self._client = client
        self._deployment = deployment_name
        self._retry_max_attempts = retry_max_attempts
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds
        log.info(
            "AzureOpenAIEmbeddingFunction ready: deployment=%s endpoint=%s",
            deployment_name,
            endpoint,
        )

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        """Return embeddings for *input* texts (ChromaDB protocol)."""
        if not input:
            return []
        try:
            response = retry_sync(
                self._client.embeddings.create,
                model=self._deployment,
                input=input,
                source="azure_embeddings",
                max_attempts=self._retry_max_attempts,
                base_delay=self._retry_base_delay_seconds,
                max_delay=self._retry_max_delay_seconds,
                retryable_exceptions=(Exception,),
                retry_if=_is_transient_azure_error,
            )
        except RetryExhaustedError as error:
            raise AzureEmbeddingServiceError(
                "Azure OpenAI embedding request failed after "
                f"{error.attempts} attempt(s): {error.envelope.message}"
            ) from error
        except Exception as error:
            status_code = getattr(error, "status_code", None)
            status = f"HTTP {status_code}" if isinstance(status_code, int) else "a client error"
            raise AzureEmbeddingServiceError(
                "Azure OpenAI rejected the embedding request "
                f"({status}). Verify AZURE_OPENAI_ENDPOINT and "
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT."
            ) from error
        embeddings = getattr(response, "data", None)
        if not isinstance(embeddings, list) or len(embeddings) != len(input):
            raise RuntimeError("Azure OpenAI returned an invalid embedding response.")
        vectors: list[list[float]] = []
        for item in embeddings:
            vector = getattr(item, "embedding", None)
            if not isinstance(vector, list) or not vector:
                raise RuntimeError("Azure OpenAI returned an invalid embedding vector.")
            if not all(isinstance(value, (int, float)) for value in vector):
                raise RuntimeError("Azure OpenAI returned a non-numeric embedding vector.")
            vectors.append([float(value) for value in vector])
        return vectors


class AzureEmbeddingServiceError(RuntimeError):
    """An actionable Azure embedding service failure without secret values."""


def azure_embedding_collection_name(deployment_name: str) -> str:
    """Return a stable collection name that cannot mix local and Azure vectors."""
    digest = hashlib.sha256(deployment_name.encode("utf-8")).hexdigest()[:12]
    return f"{_CHROMA_COLLECTION}_azure_{digest}"


def _uses_openai_compatible_base_url(endpoint: str) -> bool:
    parsed_endpoint = urlsplit(endpoint)
    hostname = parsed_endpoint.hostname or ""
    return hostname.endswith(".services.ai.azure.com") or parsed_endpoint.path.rstrip(
        "/"
    ).endswith("/openai/v1")


def _openai_compatible_base_url(endpoint: str) -> str:
    """Normalize Foundry resource/project endpoints to the OpenAI v1 base path."""
    base_url = endpoint.rstrip("/")
    if not base_url.endswith(("/openai/v1", "/models")):
        base_url = f"{base_url}/openai/v1"
    return f"{base_url}/"


def _is_transient_azure_error(error: Exception) -> bool:
    """Retry only timeouts, transport faults, throttling, and server errors."""
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code == 408 or status_code == 429 or status_code >= 500
    return isinstance(error, (OSError, TimeoutError)) or error.__class__.__name__ in {
        "APIConnectionError",
        "APITimeoutError",
    }


# ---------------------------------------------------------------------------
# ChromaDB semantic store (requires chromadb + an explicit embedding function)
# ---------------------------------------------------------------------------


def _chroma_available() -> bool:
    try:
        import chromadb  # noqa: F401

        return True
    except ImportError:
        return False


class ChromaRuleStore:
    """Semantic policy retrieval using ChromaDB and a configured embedding service."""

    def __init__(
        self,
        chroma_path: Path,
        relevance_threshold: float = 0.2,
        collection_name: str = _CHROMA_COLLECTION,
        embedding_function: object | None = None,
        retry_max_attempts: int = 2,
        retry_base_delay_seconds: float = 0.5,
        retry_max_delay_seconds: float = 5,
    ) -> None:
        if not _chroma_available():
            raise RuntimeError(
                "chromadb is not installed. "
                "Install the project requirements before building the policy index."
            )
        if embedding_function is None:
            raise ValueError(
                "An embedding_function is required. Configure Azure OpenAI embeddings "
                "and run `python -m src.rag.ingest --azure-embeddings`."
            )
        if not 0 <= relevance_threshold <= 1:
            raise ValueError("relevance_threshold must be between 0 and 1")

        import chromadb
        from chromadb.config import Settings

        self._threshold = relevance_threshold
        self._retry_max_attempts = retry_max_attempts
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds
        self._client = self._retry_chroma(
            chromadb.PersistentClient,
            path=str(chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._ef = embedding_function
        self._collection = self._retry_chroma(
            self._client.get_or_create_collection,
            name=collection_name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        log.debug(
            "ChromaRuleStore ready: path=%s collection=%s items=%d",
            chroma_path,
            collection_name,
            self._retry_chroma(self._collection.count),
        )

    def _retry_chroma(self, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Retry transient local-store contention without hiding a final failure."""
        try:
            return retry_sync(
                operation,
                *args,
                source="chromadb",
                max_attempts=self._retry_max_attempts,
                base_delay=self._retry_base_delay_seconds,
                max_delay=self._retry_max_delay_seconds,
                retryable_exceptions=(OSError, sqlite3.OperationalError),
                **kwargs,
            )
        except RetryExhaustedError as error:
            raise RuntimeError(
                f"ChromaDB failed after {error.attempts} attempt(s): {error.envelope.message}"
            ) from error

    # ------------------------------------------------------------------
    # Write side
    # ------------------------------------------------------------------

    def upsert_rules(self, rules: tuple[PolicyRule, ...]) -> None:
        """Add or replace all rules in the collection."""
        if not rules:
            return
        self._retry_chroma(
            self._collection.upsert,
            ids=[rule.rule_id for rule in rules],
            documents=[rule.content for rule in rules],
            metadatas=[
                {
                    "source": rule.source,
                    "source_hash": rule.source_hash,
                }
                for rule in rules
            ],
        )
        log.info("ChromaRuleStore upserted %d rule(s).", len(rules))

    def delete_collection(self) -> None:
        """Remove all documents — used before a full re-ingest."""
        self._retry_chroma(self._client.delete_collection, self._collection.name)
        # Re-create empty so the store remains usable
        self._collection = self._retry_chroma(
            self._client.get_or_create_collection,
            name=self._collection.name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------

    def retrieve(self, query: str, limit: int = 4) -> tuple[str, ...]:
        """Return content strings above the relevance threshold."""
        return tuple(result.rule.content for result in self.search(query, limit))

    def search(self, query: str, limit: int = 4) -> tuple[RetrievedPolicy, ...]:
        """Return scored policy evidence. Score = 1 - cosine_distance (0–1)."""
        if limit < 1 or not query.strip():
            return ()
        if self._retry_chroma(self._collection.count) == 0:
            return ()

        count = self._retry_chroma(self._collection.count)
        results = self._retry_chroma(
            self._collection.query,
            query_texts=[query],
            n_results=min(limit, count),
            include=["documents", "metadatas", "distances"],
        )

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        matches = []
        for rule_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score in [0, 1]
            score = round(max(0.0, 1.0 - dist / 2.0), 4)
            if score >= self._threshold:
                rule = PolicyRule(
                    rule_id=rule_id,
                    content=doc,
                    source=meta.get("source", "unknown"),
                    source_hash=meta.get("source_hash", ""),
                )
                matches.append(RetrievedPolicy(rule=rule, score=score))

        matches.sort(key=lambda r: (-r.score, r.rule.rule_id))
        return tuple(matches)

    @property
    def count(self) -> int:
        """Number of rules currently stored in the collection."""
        return self._retry_chroma(self._collection.count)

    def close(self) -> None:
        """Close client resources if supported."""
        if hasattr(self._client, "_system") and hasattr(self._client._system, "stop"):
            try:
                self._client._system.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_rules(
    content: str,
    *,
    source_hash: str,
    source_name: str,
) -> tuple[PolicyRule, ...]:
    sections = re.split(r"(?m)^##\s+", content)
    rules = []
    for index, section in enumerate(sections):
        cleaned = section.strip()
        if not cleaned or "\n" not in cleaned:
            continue
        title, body = cleaned.split("\n", 1)
        match = _RULE_HEADING.match(title.strip())
        rule_id = match.group(1) if match else f"POLICY-{index:03d}"
        content = f"{title.strip()}\n{body.strip()}"
        if body.strip():
            rules.append(
                PolicyRule(
                    rule_id=rule_id,
                    content=content,
                    source=source_name,
                    source_hash=source_hash,
                )
            )
    return tuple(rules)


def _terms(value: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-zA-Z_]{3,}", value.lower())
        if term not in _STOP_WORDS
    }
