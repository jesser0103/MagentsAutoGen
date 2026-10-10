"""Unit tests for Phase 4 FinOps and reliability utilities (MA-701–707)."""

from __future__ import annotations

import json
import logging
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from opentelemetry import trace

from src.utils.cost_tracker import (
    ESTIMATE_DISCLAIMER,
    CostTracker,
    SessionCostSummary,
    TokenUsageRecord,
    load_pricing,
)
from src.utils.retry import (
    ErrorEnvelope,
    RetryExhaustedError,
    retry_async,
    retry_sync,
    with_retry,
)
from src.utils.structured_logging import (
    _RedactingJsonFormatter,
    configure_logging,
    get_run_id,
    run_logging_context,
    set_run_id,
)

# ---------------------------------------------------------------------------
# MA-702/703 — CostTracker
# ---------------------------------------------------------------------------


class CostTrackerTests(unittest.TestCase):
    """MA-701/702/703/704 — Token recording, pricing, and cost calculation."""

    def _tracker_with_pricing(self, prices: dict) -> CostTracker:
        """Return a CostTracker backed by a temp pricing file."""
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "pricing.json"
        path.write_text(
            json.dumps({"models": prices}), encoding="utf-8"
        )
        return CostTracker(pricing_path=path)

    def test_record_captures_token_counts(self) -> None:
        tracker = CostTracker()
        record = tracker.record(
            run_id="run-1",
            agent="planner",
            stage="planning",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
        )
        self.assertIsInstance(record, TokenUsageRecord)
        self.assertEqual(record.total_tokens, 150)
        self.assertEqual(record.agent, "planner")

    def test_cost_calculation_uses_pricing_file(self) -> None:
        tracker = self._tracker_with_pricing(
            {"gpt-4o": {"input_per_1k_tokens": 0.005, "output_per_1k_tokens": 0.015}}
        )
        record = tracker.record(
            run_id="r1", agent="coder", stage="coding",
            model="gpt-4o", prompt_tokens=1000, completion_tokens=500,
        )
        breakdown = tracker.calculate_cost(record)
        # 1000 prompt tokens @ $0.005/1k = $0.005
        # 500 completion tokens @ $0.015/1k = $0.0075
        self.assertAlmostEqual(breakdown.input_cost_usd, 0.005, places=6)
        self.assertAlmostEqual(breakdown.output_cost_usd, 0.0075, places=6)
        self.assertAlmostEqual(breakdown.total_cost_usd, 0.0125, places=6)

    def test_unknown_model_falls_back_to_default_price(self) -> None:
        tracker = self._tracker_with_pricing(
            {"default": {"input_per_1k_tokens": 0.01, "output_per_1k_tokens": 0.02}}
        )
        record = tracker.record(
            run_id="r1", agent="reviewer", stage="reviewing",
            model="unknown-model-xyz", prompt_tokens=500, completion_tokens=100,
        )
        breakdown = tracker.calculate_cost(record)
        self.assertAlmostEqual(breakdown.input_cost_usd, 0.005, places=6)

    def test_missing_pricing_file_returns_zero_cost(self) -> None:
        tracker = CostTracker(pricing_path=Path("nonexistent/pricing.json"))
        record = tracker.record(
            run_id="r1", agent="coder", stage="coding",
            model="gpt-4o", prompt_tokens=1000, completion_tokens=1000,
        )
        breakdown = tracker.calculate_cost(record)
        self.assertEqual(breakdown.total_cost_usd, 0.0)

    def test_session_summary_aggregates_per_agent(self) -> None:
        tracker = self._tracker_with_pricing(
            {"gpt-4o": {"input_per_1k_tokens": 0.01, "output_per_1k_tokens": 0.01}}
        )
        tracker.record(run_id="r1", agent="planner", stage="planning",
                       model="gpt-4o", prompt_tokens=500, completion_tokens=100)
        tracker.record(run_id="r1", agent="coder", stage="coding",
                       model="gpt-4o", prompt_tokens=800, completion_tokens=400)
        tracker.record(run_id="r2", agent="planner", stage="planning",
                       model="gpt-4o", prompt_tokens=200, completion_tokens=50)

        summary = tracker.session_summary("r1")
        self.assertIsInstance(summary, SessionCostSummary)
        self.assertIn("planner", summary.per_agent)
        self.assertIn("coder", summary.per_agent)
        # r2 records must NOT appear in r1's summary
        self.assertEqual(summary.total_prompt_tokens, 1300)
        self.assertEqual(summary.total_completion_tokens, 500)

    def test_estimate_disclaimer_always_present(self) -> None:
        tracker = CostTracker()
        summary = tracker.session_summary("run-empty")
        self.assertEqual(summary.disclaimer, ESTIMATE_DISCLAIMER)

    def test_negative_token_counts_clamped_to_zero(self) -> None:
        tracker = CostTracker()
        record = tracker.record(
            run_id="r1", agent="a", stage="s",
            model="m", prompt_tokens=-10, completion_tokens=-5,
        )
        self.assertEqual(record.prompt_tokens, 0)
        self.assertEqual(record.completion_tokens, 0)


class LoadPricingTests(unittest.TestCase):
    def test_loads_model_prices_from_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pricing.json"
            path.write_text(
                json.dumps({"models": {"gpt-4": {"input_per_1k_tokens": 0.03}}}),
                encoding="utf-8",
            )
            prices = load_pricing(path)
        self.assertIn("gpt-4", prices)

    def test_missing_file_returns_empty_dict(self) -> None:
        prices = load_pricing(Path("does_not_exist.json"))
        self.assertEqual(prices, {})

    def test_malformed_json_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text("not-valid-json!!!", encoding="utf-8")
            prices = load_pricing(path)
        self.assertEqual(prices, {})


# ---------------------------------------------------------------------------
# MA-705 — Retry utilities
# ---------------------------------------------------------------------------


class RetryAsyncTests(unittest.IsolatedAsyncioTestCase):
    """MA-705 — retry_async bounded exponential backoff."""

    async def test_succeeds_on_first_attempt(self) -> None:
        calls = []

        async def fn():
            calls.append(1)
            return "ok"

        result = await retry_async(fn, source="test", max_attempts=3,
                                   base_delay=0, max_delay=0)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 1)

    async def test_retries_on_transient_error(self) -> None:
        calls = []

        async def fn():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("transient")
            return "recovered"

        result = await retry_async(fn, source="test", max_attempts=5,
                                   base_delay=0, max_delay=0)
        self.assertEqual(result, "recovered")
        self.assertEqual(len(calls), 3)

    async def test_raises_retry_exhausted_after_all_attempts(self) -> None:
        async def always_fails():
            raise OSError("permanent")

        with self.assertRaises(RetryExhaustedError) as ctx:
            await retry_async(always_fails, source="svc", max_attempts=2,
                              base_delay=0, max_delay=0)
        self.assertEqual(ctx.exception.attempts, 2)
        self.assertEqual(ctx.exception.envelope.source, "svc")


class RetrySyncTests(unittest.TestCase):
    """MA-705 — retry_sync bounded exponential backoff."""

    def test_succeeds_on_first_attempt(self) -> None:
        result = retry_sync(lambda: "done", source="s", max_attempts=3,
                            base_delay=0, max_delay=0)
        self.assertEqual(result, "done")

    def test_retries_and_succeeds(self) -> None:
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("transient")
            return "ok"

        result = retry_sync(fn, source="s", max_attempts=3, base_delay=0, max_delay=0)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)

    def test_with_retry_decorator(self) -> None:
        calls = []

        @with_retry(source="dec", max_attempts=3, base_delay=0, max_delay=0)
        def fn():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("boom")
            return "decorated"

        result = fn()
        self.assertEqual(result, "decorated")
        self.assertEqual(len(calls), 2)


class ErrorEnvelopeTests(unittest.TestCase):
    def test_from_exception_captures_message(self) -> None:
        exc = ValueError("something went wrong")
        envelope = ErrorEnvelope.from_exception(exc, source="test", retryable=True)
        self.assertEqual(envelope.message, "something went wrong")
        self.assertEqual(envelope.source, "test")
        self.assertTrue(envelope.retryable)

    def test_to_dict_contains_required_keys(self) -> None:
        envelope = ErrorEnvelope(source="s", message="m", retryable=False)
        d = envelope.to_dict()
        for key in ("source", "message", "retryable", "timestamp"):
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# MA-707 — Structured JSON logging
# ---------------------------------------------------------------------------


class StructuredLoggingTests(unittest.TestCase):
    def _format(self, message: str, level: int = logging.INFO) -> dict:
        """Format a synthetic log record directly via the JSON formatter."""
        set_run_id("test-run-999")
        formatter = _RedactingJsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname="test_file.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        set_run_id(None)
        return json.loads(output)

    def test_output_is_valid_json(self) -> None:
        record = self._format("hello from test")
        self.assertIsInstance(record, dict)

    def test_required_fields_present(self) -> None:
        record = self._format("check fields")
        for field in ("timestamp", "level", "logger", "service", "message"):
            self.assertIn(field, record, f"Missing field: {field}")

    def test_run_id_is_injected(self) -> None:
        record = self._format("with run_id")
        self.assertEqual(record.get("run_id"), "test-run-999")

    def test_api_key_is_redacted(self) -> None:
        # Use a pattern that matches _VALUE_PATTERNS in redaction.py (api_key=value).
        record = self._format("api_key=supersecretvalue123 endpoint=https://example.com")
        message = record.get("message", "")
        self.assertNotIn("supersecretvalue123", message, f"Secret leaked in message: {message}")

    def test_schema_version_is_integer(self) -> None:
        record = self._format("version check")
        self.assertIsInstance(record.get("schema_version"), int)

    def test_trace_and_span_ids_are_injected(self) -> None:
        formatter = _RedactingJsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=1,
            msg="correlated",
            args=(),
            exc_info=None,
        )
        span_context = trace.SpanContext(
            trace_id=0x123,
            span_id=0x456,
            is_remote=False,
            trace_flags=trace.TraceFlags(1),
        )
        with trace.use_span(trace.NonRecordingSpan(span_context)):
            payload = json.loads(formatter.format(record))

        self.assertEqual(payload["trace_id"], format(0x123, "032x"))
        self.assertEqual(payload["span_id"], format(0x456, "016x"))

    def test_run_logging_context_restores_the_parent_context(self) -> None:
        set_run_id("outer")
        with run_logging_context("inner"):
            self.assertEqual(get_run_id(), "inner")
        self.assertEqual(get_run_id(), "outer")
        set_run_id(None)

    def test_configure_logging_does_not_raise(self) -> None:
        """configure_logging() should complete without error."""
        configure_logging(level=logging.WARNING, stream=StringIO())
