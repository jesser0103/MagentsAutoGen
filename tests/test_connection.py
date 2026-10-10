import unittest

from src.app_factory import create_orchestrator
from src.config.settings import ApplicationSettings, SettingsError
from src.security.sandbox import SandboxWorkerClient


class ApplicationSettingsTests(unittest.TestCase):
    def test_loads_complete_chat_configuration(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "AZURE_OPENAI_API_KEY": "unit-test-key",
                "AZURE_OPENAI_API_VERSION": "2025-01-01-preview",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
                "MAGENT_MAX_REVIEW_ROUNDS": "5",
            }
        )

        settings.azure_openai.require_chat_settings()

        self.assertEqual(settings.azure_openai.deployment_name, "gpt-4o")
        self.assertEqual(settings.max_review_rounds, 5)
        self.assertEqual(settings.azure_openai.as_safe_dict()["api_key"], "***")

    def test_reports_missing_settings_without_reading_a_live_environment(self) -> None:
        settings = ApplicationSettings.from_environment({"AZURE_OPENAI_ENDPOINT": "https://example"})

        with self.assertRaisesRegex(SettingsError, "AZURE_OPENAI_API_KEY"):
            settings.azure_openai.require_chat_settings()

    def test_accepts_a_foundry_endpoint_without_an_api_version(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.services.ai.azure.com/models",
                "AZURE_OPENAI_API_KEY": "unit-test-key",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            }
        )

        settings.azure_openai.require_chat_settings()

        self.assertTrue(settings.azure_openai.uses_openai_compatible_base_url)
        self.assertEqual(
            settings.azure_openai.openai_compatible_base_url,
            "https://example.services.ai.azure.com/models/",
        )

    def test_normalizes_a_foundry_resource_endpoint_to_openai_v1(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.services.ai.azure.com",
                "AZURE_OPENAI_API_KEY": "unit-test-key",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            }
        )

        self.assertEqual(
            settings.azure_openai.openai_compatible_base_url,
            "https://example.services.ai.azure.com/openai/v1/",
        )

    def test_requires_an_api_version_for_direct_azure_openai(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "AZURE_OPENAI_API_KEY": "unit-test-key",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
            }
        )

        with self.assertRaisesRegex(SettingsError, "AZURE_OPENAI_API_VERSION"):
            settings.azure_openai.require_chat_settings()

    def test_rejects_invalid_review_round_limit(self) -> None:
        with self.assertRaisesRegex(SettingsError, "MAGENT_MAX_REVIEW_ROUNDS"):
            ApplicationSettings.from_environment({"MAGENT_MAX_REVIEW_ROUNDS": "0"})

    def test_rejects_invalid_rag_relevance_threshold(self) -> None:
        with self.assertRaisesRegex(SettingsError, "MAGENT_RAG_RELEVANCE_THRESHOLD"):
            ApplicationSettings.from_environment({"MAGENT_RAG_RELEVANCE_THRESHOLD": "1.1"})

    def test_rejects_small_context_budget(self) -> None:
        with self.assertRaisesRegex(SettingsError, "MAGENT_MAX_CONTEXT_CHARACTERS"):
            ApplicationSettings.from_environment({"MAGENT_MAX_CONTEXT_CHARACTERS": "255"})

    def test_composition_root_injects_operational_limits(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "MAGENT_SCANNER_TIMEOUT_SECONDS": "7",
                "MAGENT_SANDBOX_TIMEOUT_SECONDS": "9",
                "MAGENT_MAX_INPUT_CHARACTERS": "321",
            }
        )

        orchestrator = create_orchestrator(settings=settings)

        self.assertEqual(orchestrator.scanner.timeout_seconds, 7)
        self.assertEqual(orchestrator.sandbox.timeout_seconds, 9)
        self.assertEqual(orchestrator.input_screen.max_characters, 321)

    def test_composition_root_uses_remote_sandbox_worker_when_configured(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "MAGENT_SANDBOX_URL": "http://sandbox:8081",
                "MAGENT_SANDBOX_TIMEOUT_SECONDS": "15",
            }
        )

        orchestrator = create_orchestrator(settings=settings)

        self.assertIsInstance(orchestrator.sandbox, SandboxWorkerClient)
        self.assertEqual(orchestrator.sandbox.endpoint, "http://sandbox:8081")
        self.assertEqual(orchestrator.sandbox.timeout_seconds, 15)

    def test_rejects_invalid_sandbox_worker_url(self) -> None:
        with self.assertRaisesRegex(SettingsError, "MAGENT_SANDBOX_URL"):
            ApplicationSettings.from_environment(
                {"MAGENT_SANDBOX_URL": "sandbox:8081"}
            )

    def test_reads_content_safety_timeout(self) -> None:
        settings = ApplicationSettings.from_environment(
            {"MAGENT_CONTENT_SAFETY_TIMEOUT_SECONDS": "22"}
        )

        self.assertEqual(settings.content_safety_timeout_seconds, 22)

    def test_embedding_settings_do_not_require_a_chat_deployment(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "AZURE_OPENAI_API_KEY": "unit-test-key",
                "AZURE_OPENAI_API_VERSION": "2024-10-21",
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
            }
        )

        settings.require_embedding_settings()

    def test_embedding_settings_require_a_deployment(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "AZURE_OPENAI_API_KEY": "unit-test-key",
                "AZURE_OPENAI_API_VERSION": "2024-10-21",
            }
        )

        with self.assertRaisesRegex(SettingsError, "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"):
            settings.require_embedding_settings()

    def test_composition_root_injects_adapter_retry_policy(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "MAGENT_ADAPTER_RETRY_MAX_ATTEMPTS": "4",
                "MAGENT_ADAPTER_RETRY_BASE_SECONDS": "0.25",
                "MAGENT_ADAPTER_RETRY_MAX_SECONDS": "2",
            }
        )

        orchestrator = create_orchestrator(settings=settings)

        self.assertEqual(orchestrator.scanner.retry_max_attempts, 4)
        self.assertEqual(orchestrator.scanner.retry_base_delay_seconds, 0.25)
        self.assertEqual(orchestrator.sandbox.retry_max_delay_seconds, 2)
