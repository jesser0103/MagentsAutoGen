"""Structured JSON logging for MagentAutoGen (MA-707).

Sets up an OpenTelemetry-compatible JSON log handler that:
* Emits every log record as a single-line JSON object.
* Never includes prompt text or secrets by default — string values pass
  through :func:`src.utils.redaction.redact_text` before serialisation.
* Adds ``service``, ``run_id`` (when available), and ``schema_version``
  fields so log aggregators can correlate records with workflow runs.

Usage
-----
Call :func:`configure_logging` once at application start-up::

    from src.utils.structured_logging import configure_logging
    configure_logging(level=logging.INFO)

After that, any ``logging.getLogger(__name__)`` call automatically emits
structured JSON to ``stderr``.  Existing ``print``-based output is unaffected.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from opentelemetry import trace

from src.utils.redaction import redact_text

_LOG_SCHEMA_VERSION = 1
_SERVICE_NAME = "magent-autogen"

# Context-local correlation survives ``await`` boundaries without leaking one
# concurrent workflow's run ID into another workflow's logs.
_CURRENT_RUN_ID: ContextVar[str | None] = ContextVar(
    "magent_log_run_id",
    default=None,
)


def set_run_id(run_id: str | None) -> None:
    """Set the run ID that will be attached to every subsequent log record."""
    _CURRENT_RUN_ID.set(run_id)


def get_run_id() -> str | None:
    """Return the currently active run ID, or ``None``."""
    return _CURRENT_RUN_ID.get()


@contextmanager
def run_logging_context(run_id: str) -> Iterator[None]:
    """Attach *run_id* to logs for the lifetime of the current async context."""
    token = _CURRENT_RUN_ID.set(run_id)
    try:
        yield
    finally:
        _CURRENT_RUN_ID.reset(token)


class _RedactingJsonFormatter(logging.Formatter):
    """Format log records as single-line JSON with secret redaction (MA-707)."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # Populate record.message which %(message)s requires.
        record.message = record.getMessage()
        safe_message = redact_text(record.message)

        payload: dict[str, Any] = {
            "schema_version": _LOG_SCHEMA_VERSION,
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": _SERVICE_NAME,
            "message": safe_message,
        }

        # Correlation fields
        run_id = _CURRENT_RUN_ID.get()
        if run_id:
            payload["run_id"] = run_id

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format(span_context.trace_id, "032x")
            payload["span_id"] = format(span_context.span_id, "016x")

        # A small allowlist keeps structured workflow metadata queryable while
        # avoiding accidental serialization of prompts or arbitrary objects.
        for field_name in ("event_type", "operation", "stage", "status", "agent"):
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = redact_text(str(value))

        # Exception info — include type and message only (no full traceback in JSON).
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else "Unknown",
                "message": redact_text(str(exc_value)) if exc_value else "",
            }

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    level: int = logging.INFO,
    stream: Any = None,
    *,
    include_plain_handler: bool = False,
) -> None:
    """Configure the root logger to emit structured JSON records (MA-707).

    Parameters
    ----------
    level:
        Logging level (e.g. ``logging.DEBUG``, ``logging.INFO``).
    stream:
        Output stream.  Defaults to ``sys.stderr``.
    include_plain_handler:
        If ``True``, also attach a plain ``StreamHandler`` for human-readable
        output during development.  Defaults to ``False`` (JSON only).
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any handlers added by earlier basicConfig calls.
    root.handlers.clear()

    json_handler = logging.StreamHandler(stream or sys.stderr)
    json_handler.setFormatter(_RedactingJsonFormatter())
    json_handler.setLevel(level)
    root.addHandler(json_handler)

    if include_plain_handler:
        plain_handler = logging.StreamHandler(sys.stdout)
        plain_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
        )
        plain_handler.setLevel(level)
        root.addHandler(plain_handler)

    logging.getLogger(__name__).debug(
        "Structured JSON logging configured (level=%s, schema_version=%d)",
        logging.getLevelName(level),
        _LOG_SCHEMA_VERSION,
    )
