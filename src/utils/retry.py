"""Retry helpers and structured error envelopes for MagentAutoGen (MA-705).

Provides:
* :class:`ErrorEnvelope` — a typed, structured error record that wraps any
  recoverable or terminal failure with source, timestamp, and retryability.
* :func:`retry_async` — bounded exponential backoff for ``async`` callables.
* :func:`retry_sync` — bounded exponential backoff for synchronous callables.

These wrappers are used by Azure OpenAI calls, ChromaDB, scanner subprocesses,
and Docker invocations so that transient failures surface a clean
``ErrorEnvelope`` rather than a raw exception.

Design notes
------------
* Back-off is ``base * 2^attempt`` capped at ``max_delay_seconds``.
* Jitter is not added here — callers that fan out many parallel requests should
  add their own jitter to avoid thundering-herd issues.
* The retry loop logs each attempt at ``WARNING`` level so that retry storms are
  visible in structured logs without polluting ``INFO`` output.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

log = logging.getLogger(__name__)

_T = TypeVar("_T")

# Exceptions that are always treated as non-retryable (programming errors).
_NEVER_RETRY = (KeyboardInterrupt, SystemExit, MemoryError)


# ---------------------------------------------------------------------------
# Error envelope (MA-705)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorEnvelope:
    """Structured error record for any MagentAutoGen component failure (MA-705).

    Attributes
    ----------
    source:
        Component that raised the error (e.g. ``"azure_openai"``, ``"chromadb"``,
        ``"bandit"``, ``"docker_sandbox"``).
    message:
        Human-readable error description.  Must not contain secrets.
    retryable:
        ``True`` when the caller may safely retry the operation.
    timestamp:
        UTC timestamp of when the error was recorded.
    details:
        Optional extra context (e.g. HTTP status code, exit code).
    """

    source: str
    message: str
    retryable: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "message": self.message,
            "retryable": self.retryable,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        source: str,
        retryable: bool = True,
        details: dict[str, Any] | None = None,
    ) -> "ErrorEnvelope":
        """Wrap a raw exception in an envelope."""
        return cls(
            source=source,
            message=str(exc),
            retryable=retryable,
            details=details or {},
        )


class RetryExhaustedError(RuntimeError):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, envelope: ErrorEnvelope, attempts: int) -> None:
        super().__init__(
            f"[{envelope.source}] Retry exhausted after {attempts} attempt(s): "
            f"{envelope.message}"
        )
        self.envelope = envelope
        self.attempts = attempts


# ---------------------------------------------------------------------------
# Retry decorators (MA-705)
# ---------------------------------------------------------------------------


async def retry_async(
    func: Callable[..., Any],
    *args: Any,
    source: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    retry_if: Callable[[Exception], bool] | None = None,
    **kwargs: Any,
) -> Any:
    """Call an ``async`` callable with bounded exponential backoff.

    Parameters
    ----------
    func:
        The ``async`` callable to invoke.
    *args:
        Positional arguments forwarded to *func*.
    source:
        Component name for :class:`ErrorEnvelope` records.
    max_attempts:
        Maximum number of invocations (including the first).
    base_delay:
        Seconds to wait before the first retry.
    max_delay:
        Maximum seconds to wait between retries.
    retryable_exceptions:
        Exception types that trigger a retry.  All others propagate immediately.
    retry_if:
        Optional predicate for classifying caught exceptions. Returning
        ``False`` propagates the original exception immediately.
    **kwargs:
        Keyword arguments forwarded to *func*.

    Returns
    -------
    Any
        The return value of *func* on success.

    Raises
    ------
    RetryExhaustedError
        When all attempts are exhausted.
    """
    last_envelope: ErrorEnvelope | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except _NEVER_RETRY:
            raise
        except retryable_exceptions as exc:
            if retry_if is not None and not retry_if(exc):
                raise
            last_envelope = ErrorEnvelope.from_exception(
                exc, source=source, retryable=(attempt < max_attempts)
            )
            if attempt == max_attempts:
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            log.warning(
                "[%s] Attempt %d/%d failed (%s). Retrying in %.1fs.",
                source,
                attempt,
                max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    assert last_envelope is not None
    raise RetryExhaustedError(last_envelope, max_attempts)


def retry_sync(
    func: Callable[..., Any],
    *args: Any,
    source: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    retry_if: Callable[[Exception], bool] | None = None,
    **kwargs: Any,
) -> Any:
    """Call a synchronous callable with bounded exponential backoff.

    Signature mirrors :func:`retry_async` but uses ``time.sleep``.
    """
    last_envelope: ErrorEnvelope | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except _NEVER_RETRY:
            raise
        except retryable_exceptions as exc:
            if retry_if is not None and not retry_if(exc):
                raise
            last_envelope = ErrorEnvelope.from_exception(
                exc, source=source, retryable=(attempt < max_attempts)
            )
            if attempt == max_attempts:
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            log.warning(
                "[%s] Attempt %d/%d failed (%s). Retrying in %.1fs.",
                source,
                attempt,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay)

    assert last_envelope is not None
    raise RetryExhaustedError(last_envelope, max_attempts)


def with_retry(
    *,
    source: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that wraps a *synchronous* function with retry logic."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return retry_sync(
                func,
                *args,
                source=source,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_exceptions=retryable_exceptions,
                **kwargs,
            )

        return wrapper

    return decorator
