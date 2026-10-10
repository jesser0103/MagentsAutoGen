"""Environment-backed settings and validation for MagentAutoGen."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import load_dotenv


class SettingsError(RuntimeError):
    """Raised when mandatory application settings are missing or invalid."""


@dataclass(frozen=True)
class AzureOpenAISettings:
    endpoint: str | None
    api_key: str | None
    api_version: str | None
    deployment_name: str | None

    @property
    def missing_chat_settings(self) -> tuple[str, ...]:
        required = {
            "AZURE_OPENAI_ENDPOINT": self.endpoint,
            "AZURE_OPENAI_API_KEY": self.api_key,
            "AZURE_OPENAI_DEPLOYMENT_NAME": self.deployment_name,
        }
        if not self.uses_openai_compatible_base_url:
            required["AZURE_OPENAI_API_VERSION"] = self.api_version
        return tuple(name for name, value in required.items() if not value)

    @property
    def missing_embedding_settings(self) -> tuple[str, ...]:
        required = {
            "AZURE_OPENAI_ENDPOINT": self.endpoint,
            "AZURE_OPENAI_API_KEY": self.api_key,
        }
        if not self.uses_openai_compatible_base_url:
            required["AZURE_OPENAI_API_VERSION"] = self.api_version
        return tuple(name for name, value in required.items() if not value)

    @property
    def uses_openai_compatible_base_url(self) -> bool:
        if not self.endpoint:
            return False
        parsed_endpoint = urlsplit(self.endpoint)
        hostname = parsed_endpoint.hostname or ""
        path = parsed_endpoint.path.rstrip("/")
        return hostname.endswith(".services.ai.azure.com") or path.endswith("/openai/v1")

    @property
    def openai_compatible_base_url(self) -> str:
        if not self.endpoint:
            raise SettingsError("Missing Azure OpenAI settings: AZURE_OPENAI_ENDPOINT")
        base_url = self.endpoint.rstrip("/")
        if not base_url.endswith(("/openai/v1", "/models")):
            base_url = f"{base_url}/openai/v1"
        return f"{base_url}/"

    def require_chat_settings(self) -> None:
        if self.missing_chat_settings:
            names = ", ".join(self.missing_chat_settings)
            raise SettingsError(f"Missing Azure OpenAI settings: {names}")

    def as_safe_dict(self) -> dict[str, str | None]:
        return {
            "endpoint": self.endpoint,
            "api_version": self.api_version,
            "deployment_name": self.deployment_name,
            "api_key": "***" if self.api_key else None,
        }


@dataclass(frozen=True)
class ApplicationSettings:
    azure_openai: AzureOpenAISettings
    embedding_deployment: str | None
    content_safety_endpoint: str | None
    content_safety_key: str | None
    content_safety_timeout_seconds: float
    checkpoint_dir: Path
    chroma_dir: Path
    pricing_file: Path
    rag_relevance_threshold: float
    max_context_characters: int
    max_review_rounds: int
    # MA-706 — Explicit operational limits
    max_context_tokens: int
    max_tokens: int
    scanner_timeout_seconds: float
    sandbox_timeout_seconds: float
    sandbox_url: str | None
    max_input_characters: int
    conversation_log_dir: Path
    llm_retry_max_attempts: int
    llm_retry_base_delay_seconds: float
    llm_retry_max_delay_seconds: float
    adapter_retry_max_attempts: int
    adapter_retry_base_delay_seconds: float
    adapter_retry_max_delay_seconds: float
    database_url: str | None = None

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        dotenv_path: str | Path | None = None,
    ) -> "ApplicationSettings":
        if environment is None:
            load_dotenv(dotenv_path=dotenv_path, override=False)
            environment = os.environ

        def value(name: str) -> str | None:
            raw_value = environment.get(name)
            return raw_value.strip() if raw_value and raw_value.strip() else None

        max_review_rounds = _positive_integer(
            value("MAGENT_MAX_REVIEW_ROUNDS") or "5", "MAGENT_MAX_REVIEW_ROUNDS"
        )
        rag_relevance_threshold = _unit_interval(
            value("MAGENT_RAG_RELEVANCE_THRESHOLD") or "0.2",
            "MAGENT_RAG_RELEVANCE_THRESHOLD",
        )
        max_context_characters = _minimum_integer(
            value("MAGENT_MAX_CONTEXT_CHARACTERS") or "6000",
            "MAGENT_MAX_CONTEXT_CHARACTERS",
            minimum=256,
        )
        # MA-706 — explicit operational limits
        max_context_tokens = _minimum_integer(
            value("MAGENT_MAX_CONTEXT_TOKENS") or "8000",
            "MAGENT_MAX_CONTEXT_TOKENS",
            minimum=256,
        )
        max_tokens = _positive_integer(
            value("MAGENT_MAX_TOKENS") or "2048",
            "MAGENT_MAX_TOKENS",
        )
        scanner_timeout_seconds = _positive_float(
            value("MAGENT_SCANNER_TIMEOUT_SECONDS") or "60",
            "MAGENT_SCANNER_TIMEOUT_SECONDS",
        )
        sandbox_timeout_seconds = _positive_float(
            value("MAGENT_SANDBOX_TIMEOUT_SECONDS") or "120",
            "MAGENT_SANDBOX_TIMEOUT_SECONDS",
        )
        sandbox_url = value("MAGENT_SANDBOX_URL")
        if sandbox_url:
            parsed_sandbox_url = urlsplit(sandbox_url)
            if (
                parsed_sandbox_url.scheme not in {"http", "https"}
                or not parsed_sandbox_url.hostname
            ):
                raise SettingsError("MAGENT_SANDBOX_URL must be an HTTP or HTTPS URL")
        max_input_characters = _minimum_integer(
            value("MAGENT_MAX_INPUT_CHARACTERS") or "4000",
            "MAGENT_MAX_INPUT_CHARACTERS",
            minimum=64,
        )
        content_safety_timeout_seconds = _positive_float(
            value("MAGENT_CONTENT_SAFETY_TIMEOUT_SECONDS") or "15",
            "MAGENT_CONTENT_SAFETY_TIMEOUT_SECONDS",
        )
        llm_retry_max_attempts = _positive_integer(
            value("MAGENT_LLM_RETRY_MAX_ATTEMPTS") or "2",
            "MAGENT_LLM_RETRY_MAX_ATTEMPTS",
        )
        llm_retry_base_delay_seconds = _non_negative_float(
            value("MAGENT_LLM_RETRY_BASE_SECONDS") or "1",
            "MAGENT_LLM_RETRY_BASE_SECONDS",
        )
        llm_retry_max_delay_seconds = _non_negative_float(
            value("MAGENT_LLM_RETRY_MAX_SECONDS") or "8",
            "MAGENT_LLM_RETRY_MAX_SECONDS",
        )
        if llm_retry_max_delay_seconds < llm_retry_base_delay_seconds:
            raise SettingsError(
                "MAGENT_LLM_RETRY_MAX_SECONDS must be greater than or equal to "
                "MAGENT_LLM_RETRY_BASE_SECONDS"
            )
        adapter_retry_max_attempts = _positive_integer(
            value("MAGENT_ADAPTER_RETRY_MAX_ATTEMPTS") or "2",
            "MAGENT_ADAPTER_RETRY_MAX_ATTEMPTS",
        )
        adapter_retry_base_delay_seconds = _non_negative_float(
            value("MAGENT_ADAPTER_RETRY_BASE_SECONDS") or "0.5",
            "MAGENT_ADAPTER_RETRY_BASE_SECONDS",
        )
        adapter_retry_max_delay_seconds = _non_negative_float(
            value("MAGENT_ADAPTER_RETRY_MAX_SECONDS") or "5",
            "MAGENT_ADAPTER_RETRY_MAX_SECONDS",
        )
        if adapter_retry_max_delay_seconds < adapter_retry_base_delay_seconds:
            raise SettingsError(
                "MAGENT_ADAPTER_RETRY_MAX_SECONDS must be greater than or equal to "
                "MAGENT_ADAPTER_RETRY_BASE_SECONDS"
            )
        return cls(
            azure_openai=AzureOpenAISettings(
                endpoint=value("AZURE_OPENAI_ENDPOINT"),
                api_key=value("AZURE_OPENAI_API_KEY"),
                api_version=value("AZURE_OPENAI_API_VERSION"),
                deployment_name=value("AZURE_OPENAI_DEPLOYMENT_NAME")
                or value("AZURE_OPENAI_CHAT_MODEL"),
            ),
            embedding_deployment=value("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            content_safety_endpoint=value("CONTENT_SAFETY_ENDPOINT"),
            content_safety_key=value("CONTENT_SAFETY_KEY"),
            content_safety_timeout_seconds=content_safety_timeout_seconds,
            checkpoint_dir=Path(value("MAGENT_CHECKPOINT_DIR") or "data/checkpoints"),
            chroma_dir=Path(value("MAGENT_CHROMA_DIR") or "data/chroma"),
            pricing_file=Path(value("MAGENT_PRICING_FILE") or "config/pricing.json"),
            rag_relevance_threshold=rag_relevance_threshold,
            max_context_characters=max_context_characters,
            max_review_rounds=max_review_rounds,
            max_context_tokens=max_context_tokens,
            max_tokens=max_tokens,
            scanner_timeout_seconds=scanner_timeout_seconds,
            sandbox_timeout_seconds=sandbox_timeout_seconds,
            sandbox_url=sandbox_url,
            max_input_characters=max_input_characters,
            conversation_log_dir=Path(
                value("MAGENT_CONVERSATION_LOG_DIR") or "data/conversations"
            ),
            llm_retry_max_attempts=llm_retry_max_attempts,
            llm_retry_base_delay_seconds=llm_retry_base_delay_seconds,
            llm_retry_max_delay_seconds=llm_retry_max_delay_seconds,
            adapter_retry_max_attempts=adapter_retry_max_attempts,
            adapter_retry_base_delay_seconds=adapter_retry_base_delay_seconds,
            adapter_retry_max_delay_seconds=adapter_retry_max_delay_seconds,
            database_url=value("MAGENT_DATABASE_URL") or value("DATABASE_URL"),
        )

    @property
    def content_safety_configured(self) -> bool:
        return bool(self.content_safety_endpoint and self.content_safety_key)

    def require_content_safety_settings(self) -> None:
        missing = []
        if not self.content_safety_endpoint:
            missing.append("CONTENT_SAFETY_ENDPOINT")
        if not self.content_safety_key:
            missing.append("CONTENT_SAFETY_KEY")
        if missing:
            raise SettingsError(f"Missing Azure AI Content Safety settings: {', '.join(missing)}")

    def require_embedding_settings(self) -> None:
        """Require the Azure deployment used for production policy retrieval."""
        missing = list(self.azure_openai.missing_embedding_settings)
        if not self.embedding_deployment:
            missing.append("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if missing:
            raise SettingsError(
                "Missing Azure OpenAI embedding settings: " + ", ".join(missing)
            )


def _positive_integer(raw_value: str, name: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as error:
        raise SettingsError(f"{name} must be a positive integer") from error
    if value < 1:
        raise SettingsError(f"{name} must be a positive integer")
    return value


def _positive_float(raw_value: str, name: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as error:
        raise SettingsError(f"{name} must be a positive number") from error
    if value <= 0:
        raise SettingsError(f"{name} must be a positive number")
    return value


def _non_negative_float(raw_value: str, name: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as error:
        raise SettingsError(f"{name} must be a non-negative number") from error
    if value < 0:
        raise SettingsError(f"{name} must be a non-negative number")
    return value


def _unit_interval(raw_value: str, name: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as error:
        raise SettingsError(f"{name} must be a number between 0 and 1") from error
    if not 0 <= value <= 1:
        raise SettingsError(f"{name} must be a number between 0 and 1")
    return value


def _minimum_integer(raw_value: str, name: str, *, minimum: int) -> int:
    try:
        value = int(raw_value)
    except ValueError as error:
        raise SettingsError(f"{name} must be an integer of at least {minimum}") from error
    if value < minimum:
        raise SettingsError(f"{name} must be an integer of at least {minimum}")
    return value
