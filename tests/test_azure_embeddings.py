"""Hermetic tests for the Azure OpenAI policy-embedding adapter."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.rag.vector_store import (
    AzureEmbeddingServiceError,
    AzureOpenAIEmbeddingFunction,
    _openai_compatible_base_url,
    azure_embedding_collection_name,
)


class AzureOpenAIEmbeddingFunctionTests(unittest.TestCase):
    def test_forwards_batch_to_configured_deployment(self) -> None:
        calls: list[dict[str, object]] = []

        class Embeddings:
            def create(self, **kwargs: object) -> object:
                calls.append(kwargs)
                return SimpleNamespace(
                    data=[
                        SimpleNamespace(embedding=[0.1, 0.2]),
                        SimpleNamespace(embedding=[0.3, 0.4]),
                    ]
                )

        client = SimpleNamespace(embeddings=Embeddings())
        embedding_function = AzureOpenAIEmbeddingFunction(
            endpoint="https://example.openai.azure.com",
            api_key="not-a-real-key",
            deployment_name="policy-embeddings",
            client=client,
        )

        vectors = embedding_function(["first policy", "second policy"])

        self.assertEqual(
            calls,
            [{"model": "policy-embeddings", "input": ["first policy", "second policy"]}],
        )
        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])

    def test_rejects_malformed_embedding_response(self) -> None:
        client = SimpleNamespace(
            embeddings=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(data=[SimpleNamespace(embedding=[])])
            )
        )
        embedding_function = AzureOpenAIEmbeddingFunction(
            endpoint="https://example.openai.azure.com",
            api_key="not-a-real-key",
            deployment_name="policy-embeddings",
            client=client,
        )

        with self.assertRaisesRegex(RuntimeError, "invalid embedding vector"):
            embedding_function(["policy"])

    def test_retries_a_transient_embedding_transport_failure(self) -> None:
        calls: list[object] = []

        class Embeddings:
            def create(self, **kwargs: object) -> object:
                calls.append(kwargs)
                if len(calls) == 1:
                    raise OSError("temporary connection failure")
                return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2])])

        embedding_function = AzureOpenAIEmbeddingFunction(
            endpoint="https://example.openai.azure.com",
            api_key="not-a-real-key",
            deployment_name="policy-embeddings",
            client=SimpleNamespace(embeddings=Embeddings()),
            retry_max_attempts=2,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
        )

        self.assertEqual(embedding_function(["policy"]), [[0.1, 0.2]])
        self.assertEqual(len(calls), 2)

    def test_reports_non_retryable_azure_status_without_leaking_configuration(self) -> None:
        class NotFoundError(Exception):
            status_code = 404

        def not_found(**kwargs: object) -> object:
            raise NotFoundError()

        client = SimpleNamespace(
            embeddings=SimpleNamespace(create=not_found)
        )
        embedding_function = AzureOpenAIEmbeddingFunction(
            endpoint="https://example.openai.azure.com",
            api_key="not-a-real-key",
            deployment_name="policy-embeddings",
            client=client,
        )

        with self.assertRaisesRegex(AzureEmbeddingServiceError, "HTTP 404"):
            embedding_function(["policy"])

    def test_empty_batch_does_not_call_azure(self) -> None:
        client = SimpleNamespace(
            embeddings=SimpleNamespace(
                create=lambda **kwargs: self.fail("Azure must not be called for an empty batch")
            )
        )
        embedding_function = AzureOpenAIEmbeddingFunction(
            endpoint="https://example.openai.azure.com",
            api_key="not-a-real-key",
            deployment_name="policy-embeddings",
            client=client,
        )

        self.assertEqual(embedding_function([]), [])

    def test_collection_name_is_stable_and_deployment_isolated(self) -> None:
        first = azure_embedding_collection_name("text-embedding-3-small")

        self.assertEqual(first, azure_embedding_collection_name("text-embedding-3-small"))
        self.assertNotEqual(first, azure_embedding_collection_name("text-embedding-3-large"))
        self.assertTrue(first.startswith("magent_policies_azure_"))

    def test_foundry_endpoint_uses_openai_v1_base_path(self) -> None:
        self.assertEqual(
            _openai_compatible_base_url("https://example.services.ai.azure.com"),
            "https://example.services.ai.azure.com/openai/v1/",
        )
