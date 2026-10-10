"""OpenTelemetry setup and workflow-span helpers.

Tracing remains useful without an exporter because trace/span IDs are injected
into structured logs. Set ``OTEL_EXPORTER_OTLP_ENDPOINT`` to export spans to an
OTLP-compatible collector.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.utils.structured_logging import run_logging_context

log = logging.getLogger(__name__)

_DEFAULT_SERVICE_NAME = "magent-autogen"
_provider: TracerProvider | None = None


def configure_telemetry() -> object:
    """Configure the process tracer provider once and attach OTLP when requested."""
    global _provider  # noqa: PLW0603
    if _provider is not None:
        return _provider

    current_provider = trace.get_tracer_provider()
    if current_provider.__class__.__name__ != "ProxyTracerProvider":
        return current_provider

    service_name = os.getenv("OTEL_SERVICE_NAME", _DEFAULT_SERVICE_NAME).strip()
    _provider = TracerProvider(
        resource=Resource.create({"service.name": service_name or _DEFAULT_SERVICE_NAME})
    )
    trace.set_tracer_provider(_provider)

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            # The exporter reads endpoint, headers, certificates and timeout
            # from the standard OTEL_EXPORTER_OTLP_* environment variables.
            _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except (ImportError, ValueError):
            log.exception("OTLP tracing was requested but the exporter could not start")

    return _provider


def instrument_fastapi(app: Any) -> None:
    """Add HTTP server spans when FastAPI instrumentation is installed."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health")
    except ImportError:
        log.warning("FastAPI OpenTelemetry instrumentation is unavailable")


@contextmanager
def workflow_span(
    operation: str,
    run_id: str,
    attributes: Mapping[str, str | int | float | bool] | None = None,
) -> Iterator[trace.Span]:
    """Create a correlated workflow span and structured-log context."""
    tracer = trace.get_tracer("magent-autogen.workflow")
    span_attributes: dict[str, str | int | float | bool] = {
        "workflow.run_id": run_id,
        "workflow.operation": operation,
    }
    if attributes:
        span_attributes.update(attributes)

    with run_logging_context(run_id):
        with tracer.start_as_current_span(
            operation,
            attributes=span_attributes,
            record_exception=True,
            set_status_on_exception=True,
        ) as span:
            yield span


def add_span_event(name: str, attributes: Mapping[str, Any] | None = None) -> None:
    """Add an event to the current span when it is recording."""
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(name, attributes=dict(attributes or {}))
