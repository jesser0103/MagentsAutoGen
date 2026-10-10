"""Command-line entry point for local policy ingestion."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config.settings import ApplicationSettings, SettingsError
from src.rag.ingestion import ChromaPolicyIngestor, PolicyIngestor
from src.rag.vector_store import (
    AzureEmbeddingServiceError,
    AzureOpenAIEmbeddingFunction,
    azure_embedding_collection_name,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the local MagentAutoGen policy manifest and ChromaDB collection."
    )
    parser.add_argument(
        "sources",
        nargs="*",
        type=Path,
        help="Approved Markdown or text policy files. Defaults to data/internal_rules.txt.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/chroma/policy_manifest.json"),
        help="Local manifest path; ignored by Git by default.",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=Path("data/chroma"),
        help="ChromaDB persistence directory (default: data/chroma).",
    )
    parser.add_argument(
        "--no-chroma",
        action="store_true",
        help="Write the JSON manifest only; skip ChromaDB upsert.",
    )
    parser.add_argument(
        "--azure-embeddings",
        action="store_true",
        help=(
            "Use the Azure deployment configured in .env. Requires "
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT."
        ),
    )
    arguments = parser.parse_args()
    source_paths = tuple(arguments.sources or [Path("data/internal_rules.txt")])

    try:
        if arguments.no_chroma:
            result = PolicyIngestor().ingest(source_paths, arguments.output)
            chroma_note = " (ChromaDB skipped)"
        else:
            try:
                if arguments.azure_embeddings:
                    settings = ApplicationSettings.from_environment()
                    settings.require_embedding_settings()
                    azure_settings = settings.azure_openai
                    embedding_function = AzureOpenAIEmbeddingFunction(
                        endpoint=azure_settings.endpoint or "",
                        api_key=azure_settings.api_key or "",
                        deployment_name=settings.embedding_deployment or "",
                        api_version=azure_settings.api_version or "2024-02-01",
                        retry_max_attempts=settings.adapter_retry_max_attempts,
                        retry_base_delay_seconds=settings.adapter_retry_base_delay_seconds,
                        retry_max_delay_seconds=settings.adapter_retry_max_delay_seconds,
                    )
                    ingestor = ChromaPolicyIngestor(
                        chroma_path=arguments.chroma_dir,
                        collection_name=azure_embedding_collection_name(
                            settings.embedding_deployment or ""
                        ),
                        embedding_function=embedding_function,
                    )
                else:
                    ingestor = ChromaPolicyIngestor(chroma_path=arguments.chroma_dir)
                result = ingestor.ingest(source_paths, arguments.output)
                chroma_note = (
                    f" | {result.chroma_upserted} rule(s) upserted to ChromaDB at "
                    f"{arguments.chroma_dir}"
                )
            except (AzureEmbeddingServiceError, RuntimeError) as chroma_error:
                if arguments.azure_embeddings:
                    print(f"Azure embedding ingestion failed: {chroma_error}")
                    return 1
                # chromadb not installed — fall back gracefully
                print(f"[warn] ChromaDB unavailable ({chroma_error}); writing manifest only.")
                result = PolicyIngestor().ingest(source_paths, arguments.output)
                chroma_note = " (ChromaDB unavailable)"
    except (FileNotFoundError, SettingsError, ValueError) as error:
        print(f"Policy ingestion failed: {error}")
        return 1

    print(
        f"Policy ingestion completed: {result.chunk_count} chunk(s) from "
        f"{result.source_count} source(s) at {result.manifest_path}{chroma_note}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
