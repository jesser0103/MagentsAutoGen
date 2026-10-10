"""Model-provider contracts shared by real and local development implementations."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol

from src.utils.conversation_logger import ConversationExchange, ConversationLogger
from src.utils.cost_tracker import CostTracker
from src.utils.retry import retry_async

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelCallContext:
    """Correlation metadata supplied by the workflow for one model call."""

    run_id: str
    stage: str


_MODEL_CALL_CONTEXT: ContextVar[ModelCallContext | None] = ContextVar(
    "magent_model_call_context",
    default=None,
)


@contextmanager
def model_call_context(run_id: str, stage: str) -> Iterator[None]:
    """Correlate nested provider calls with a workflow run and stage."""
    token = _MODEL_CALL_CONTEXT.set(ModelCallContext(run_id=run_id, stage=stage))
    try:
        yield
    finally:
        _MODEL_CALL_CONTEXT.reset(token)


def get_model_call_context() -> ModelCallContext | None:
    """Return correlation metadata for the active model call, if any."""
    return _MODEL_CALL_CONTEXT.get()


class ModelProviderError(RuntimeError):
    """Raised when a model provider cannot produce a usable response."""


class ModelProvider(Protocol):
    """Minimal contract used by all specialized agents."""

    async def generate(self, name: str, instructions: str, prompt: str) -> str:
        """Return a complete text response for one specialized agent request."""


@dataclass
class AgentFrameworkProvider:
    """Adapter for the current Microsoft Agent Framework client."""

    client: object
    max_tokens: int = 2048
    model: str | None = None
    cost_tracker: CostTracker | None = None
    conversation_logger: ConversationLogger | None = None
    retry_max_attempts: int = 2
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 8.0

    def __post_init__(self) -> None:
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        if self.retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be a positive integer")
        if self.retry_base_delay_seconds < 0 or self.retry_max_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")

    async def generate(self, name: str, instructions: str, prompt: str) -> str:
        agent = self.client.as_agent(name=name, instructions=instructions)
        # Agent Framework translates max_tokens to the Chat Completions API's
        # max_completion_tokens field.
        response = await retry_async(
            agent.run,
            prompt,
            options={"max_tokens": self.max_tokens},
            source=f"azure_openai.{name}",
            max_attempts=self.retry_max_attempts,
            base_delay=self.retry_base_delay_seconds,
            max_delay=self.retry_max_delay_seconds,
            retry_if=_is_transient_model_error,
        )
        response_text = response.text or ""

        context = _MODEL_CALL_CONTEXT.get()
        run_id = context.run_id if context else "unscoped"
        stage = context.stage if context else name
        prompt_tokens, completion_tokens = _extract_usage(response)
        model = _extract_model(response, self.model, self.client)

        if self.cost_tracker is not None:
            self.cost_tracker.record(
                run_id=run_id,
                agent=name,
                stage=stage,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                max_tokens=self.max_tokens,
            )

        if self.conversation_logger is not None:
            try:
                self.conversation_logger.log_exchange(
                    ConversationExchange(
                        run_id=run_id,
                        agent=name,
                        stage=stage,
                        instructions=instructions,
                        prompt=prompt,
                        response=response_text,
                        model=model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        max_tokens=self.max_tokens,
                        finish_reason=_string_value(
                            getattr(response, "finish_reason", None)
                        ),
                    )
                )
            except OSError:
                logger.exception(
                    "Could not persist conversation exchange: run=%s agent=%s",
                    run_id,
                    name,
                )

        if not response_text:
            raise ModelProviderError(f"{name} returned an empty response")
        return response_text


def _extract_usage(response: object) -> tuple[int, int]:
    """Read Agent Framework or raw OpenAI usage fields from a response."""
    candidates = [
        getattr(response, "usage_details", None),
        getattr(response, "usage", None),
    ]
    raw_response = getattr(response, "raw_representation", None)
    if raw_response is not None:
        candidates.extend(
            [
                getattr(raw_response, "usage_details", None),
                getattr(raw_response, "usage", None),
            ]
        )

    for usage in candidates:
        if usage is None:
            continue
        prompt_tokens = _usage_value(
            usage,
            "input_token_count",
            "prompt_tokens",
            "input_tokens",
        )
        completion_tokens = _usage_value(
            usage,
            "output_token_count",
            "completion_tokens",
            "output_tokens",
        )
        if prompt_tokens is not None or completion_tokens is not None:
            return max(0, prompt_tokens or 0), max(0, completion_tokens or 0)

    logger.warning("Model response did not expose token usage; recording zero tokens")
    return 0, 0


def _usage_value(usage: object, *names: str) -> int | None:
    for name in names:
        value = usage.get(name) if isinstance(usage, Mapping) else getattr(usage, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _extract_model(response: object, configured_model: str | None, client: object) -> str:
    raw_response = getattr(response, "raw_representation", None)
    return str(
        getattr(response, "model", None)
        or getattr(raw_response, "model", None)
        or configured_model
        or getattr(client, "model", None)
        or "unknown"
    )


def _string_value(value: object) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _is_transient_model_error(error: Exception) -> bool:
    """Return whether an Azure/OpenAI failure is safe to retry.

    Only connection/timeouts and HTTP 408, 409, 429, or 5xx failures are
    retried. Authentication, validation, and quota/billing failures propagate
    immediately.
    """
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).lower()
        status_code = _status_code(current)

        if status_code == 429 and any(
            marker in message
            for marker in ("insufficient_quota", "billing", "exceeded your current quota")
        ):
            return False
        if status_code in {408, 409, 429} or (
            status_code is not None and status_code >= 500
        ):
            return True
        if isinstance(current, (TimeoutError, ConnectionError, OSError)):
            return True
        if current.__class__.__name__ in {
            "APITimeoutError",
            "APIConnectionError",
            "RateLimitError",
            "InternalServerError",
        }:
            return True

        current = current.__cause__ or current.__context__
    return False


def _status_code(error: BaseException) -> int | None:
    value = getattr(error, "status_code", None)
    if value is None:
        response = getattr(error, "response", None)
        value = getattr(response, "status_code", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@dataclass
class ScriptedModelProvider:
    """Deterministic provider for local application demos and tests."""

    responses: Sequence[str]
    position: int = 0

    async def generate(self, name: str, instructions: str, prompt: str) -> str:
        if self.position >= len(self.responses):
            raise ModelProviderError(f"No scripted response remains for {name}")
        response = self.responses[self.position]
        self.position += 1
        return response
