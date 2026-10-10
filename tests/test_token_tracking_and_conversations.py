from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from src.agents.model_provider import AgentFrameworkProvider, model_call_context
from src.config.settings import ApplicationSettings, SettingsError
from src.utils.conversation_logger import CONVERSATION_SCHEMA, ConversationLogger
from src.utils.cost_tracker import CostTracker, TokenUsageRecord
from src.workflow.models import WorkflowRun


class _FakeResponse:
    text = "api_key=should-not-be-persisted"
    finish_reason = "stop"
    usage_details = {
        "input_token_count": 37,
        "output_token_count": 11,
        "total_token_count": 48,
    }
    raw_representation = None


class _FakeAgent:
    def __init__(self) -> None:
        self.prompt: str | None = None
        self.options: dict[str, int] | None = None

    async def run(self, prompt: str, *, options: dict[str, int]):
        self.prompt = prompt
        self.options = options
        return _FakeResponse()


class _FakeClient:
    model = "test-deployment"

    def __init__(self) -> None:
        self.agent = _FakeAgent()
        self.name: str | None = None
        self.instructions: str | None = None

    def as_agent(self, *, name: str, instructions: str) -> _FakeAgent:
        self.name = name
        self.instructions = instructions
        return self.agent


class _FlakyAgent(_FakeAgent):
    def __init__(self, failures: list[Exception]) -> None:
        super().__init__()
        self.failures = failures
        self.calls = 0

    async def run(self, prompt: str, *, options: dict[str, int]):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return await super().run(prompt, options=options)


class _FlakyClient(_FakeClient):
    def __init__(self, failures: list[Exception]) -> None:
        super().__init__()
        self.agent = _FlakyAgent(failures)


class AgentFrameworkProviderTests(unittest.TestCase):
    def test_applies_limit_tracks_usage_and_logs_exchange(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tracker = CostTracker()
            conversation_logger = ConversationLogger(Path(directory))
            client = _FakeClient()
            provider = AgentFrameworkProvider(
                client,
                max_tokens=321,
                cost_tracker=tracker,
                conversation_logger=conversation_logger,
            )

            async def invoke() -> str:
                with model_call_context("run-123", "planning"):
                    return await provider.generate(
                        "planner",
                        "Keep api_key=instruction-secret safe.",
                        "Plan api_key=prompt-secret safely.",
                    )

            response = asyncio.run(invoke())
            exchanges = conversation_logger.load("run-123")

        self.assertEqual(response, _FakeResponse.text)
        self.assertEqual(client.agent.options, {"max_tokens": 321})
        records = tracker.records_for_run("run-123")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].prompt_tokens, 37)
        self.assertEqual(records[0].completion_tokens, 11)
        self.assertEqual(records[0].max_tokens, 321)
        self.assertEqual(exchanges[0]["schema"], CONVERSATION_SCHEMA)
        self.assertEqual(exchanges[0]["usage"]["total_tokens"], 48)
        self.assertNotIn("instruction-secret", str(exchanges[0]))
        self.assertNotIn("prompt-secret", str(exchanges[0]))
        self.assertNotIn("should-not-be-persisted", str(exchanges[0]))

    def test_rejects_non_positive_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            AgentFrameworkProvider(_FakeClient(), max_tokens=0)

    def test_retries_a_transient_timeout_and_records_only_the_success(self) -> None:
        tracker = CostTracker()
        client = _FlakyClient([TimeoutError("temporary timeout")])
        provider = AgentFrameworkProvider(
            client,
            cost_tracker=tracker,
            retry_max_attempts=2,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
        )

        response = asyncio.run(provider.generate("planner", "Plan safely.", "Create a plan."))

        self.assertEqual(response, _FakeResponse.text)
        self.assertEqual(client.agent.calls, 2)
        self.assertEqual(len(tracker.records_for_run("unscoped")), 1)

    def test_does_not_retry_a_non_transient_model_error(self) -> None:
        client = _FlakyClient([ValueError("invalid request")])
        provider = AgentFrameworkProvider(
            client,
            retry_max_attempts=3,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
        )

        with self.assertRaisesRegex(ValueError, "invalid request"):
            asyncio.run(provider.generate("planner", "Plan safely.", "Create a plan."))

        self.assertEqual(client.agent.calls, 1)


class TokenUsagePersistenceTests(unittest.TestCase):
    def test_usage_records_round_trip_with_workflow(self) -> None:
        run = WorkflowRun(user_request="Create a helper.")
        run.token_usage.append(
            TokenUsageRecord(
                run_id=run.run_id,
                agent="planner",
                stage="planning",
                model="deployment",
                prompt_tokens=20,
                completion_tokens=5,
                max_tokens=200,
            )
        )

        restored = WorkflowRun.from_dict(run.to_dict())

        self.assertEqual(len(restored.token_usage), 1)
        self.assertEqual(restored.token_usage[0].total_tokens, 25)
        self.assertEqual(restored.token_usage[0].record_id, run.token_usage[0].record_id)

    def test_summary_can_use_persisted_records(self) -> None:
        tracker = CostTracker()
        record = TokenUsageRecord(
            run_id="persisted-run",
            agent="coder",
            stage="coding",
            model="unknown",
            prompt_tokens=12,
            completion_tokens=3,
        )

        summary = tracker.session_summary("persisted-run", records=[record])

        self.assertEqual(summary.total_prompt_tokens, 12)
        self.assertEqual(summary.total_completion_tokens, 3)


class MaxTokensSettingsTests(unittest.TestCase):
    def test_reads_max_tokens_from_environment(self) -> None:
        settings = ApplicationSettings.from_environment(
            {"MAGENT_MAX_TOKENS": "777"}
        )
        self.assertEqual(settings.max_tokens, 777)

    def test_rejects_invalid_max_tokens(self) -> None:
        with self.assertRaises(SettingsError):
            ApplicationSettings.from_environment({"MAGENT_MAX_TOKENS": "0"})

    def test_reads_bounded_retry_settings(self) -> None:
        settings = ApplicationSettings.from_environment(
            {
                "MAGENT_LLM_RETRY_MAX_ATTEMPTS": "4",
                "MAGENT_LLM_RETRY_BASE_SECONDS": "0.25",
                "MAGENT_LLM_RETRY_MAX_SECONDS": "3",
            }
        )

        self.assertEqual(settings.llm_retry_max_attempts, 4)
        self.assertEqual(settings.llm_retry_base_delay_seconds, 0.25)
        self.assertEqual(settings.llm_retry_max_delay_seconds, 3)


if __name__ == "__main__":
    unittest.main()
