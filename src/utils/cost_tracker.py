"""FinOps cost tracker for MagentAutoGen (Sprint 7 — MA-701 through MA-707).

Tracks per-call token usage, calculates session costs from external pricing
configuration, and exposes per-agent and per-stage breakdowns for the
FinOps panel.

Design principles
-----------------
* **Prices are never hardcoded** — they are loaded from ``config/pricing.json``
  (MA-702).
* **All displayed values are estimates** — a disclaimer is surfaced in the UI
  (MA-704).
* **No secrets appear in records** — token counts and cost figures only; no
  prompt text is stored here.
* **Fail-open for FinOps** — a pricing lookup failure logs a warning and falls
  back to the ``default`` model price rather than crashing the workflow.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

log = logging.getLogger(__name__)

_DEFAULT_PRICING_PATH = Path("config/pricing.json")

# Displayed in the UI next to every cost figure (MA-704).
ESTIMATE_DISCLAIMER = (
    "These are estimates only. "
    "See Azure Cost Management for actual billing. "
    "Prices are loaded from config/pricing.json and may differ from live rates."
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenUsageRecord:
    """One model call's token usage — captured from the API response (MA-701).

    Parameters
    ----------
    run_id:
        Workflow run that triggered this call.
    agent:
        Agent name (``"planner"``, ``"coder"``, ``"reviewer"``).
    stage:
        Workflow stage (``"planning"``, ``"coding"``, ``"reviewing"``).
    model:
        Deployment / model name used for price lookup.
    prompt_tokens:
        Tokens in the prompt sent to the model.
    completion_tokens:
        Tokens in the model's completion response.
    operation:
        ``"chat"`` or ``"embedding"``.
    """

    run_id: str
    agent: str
    stage: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    operation: str = "chat"
    max_tokens: int | None = None
    record_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation for workflow persistence."""
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "agent": self.agent,
            "stage": self.stage,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "operation": self.operation,
            "max_tokens": self.max_tokens,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TokenUsageRecord":
        """Restore a persisted token-usage record."""
        created_at = value.get("created_at")
        return cls(
            record_id=str(value.get("record_id") or uuid4()),
            run_id=str(value["run_id"]),
            agent=str(value["agent"]),
            stage=str(value["stage"]),
            model=str(value["model"]),
            prompt_tokens=max(0, int(value.get("prompt_tokens", 0))),
            completion_tokens=max(0, int(value.get("completion_tokens", 0))),
            operation=str(value.get("operation") or "chat"),
            max_tokens=(
                max(1, int(value["max_tokens"]))
                if value.get("max_tokens") is not None
                else None
            ),
            created_at=(
                datetime.fromisoformat(str(created_at))
                if created_at
                else datetime.now(timezone.utc)
            ),
        )


@dataclass(frozen=True)
class CostBreakdown:
    """Calculated cost for one :class:`TokenUsageRecord` (MA-703).

    Parameters
    ----------
    record:
        The usage record this cost was calculated from.
    input_cost_usd:
        Cost for prompt (input) tokens.
    output_cost_usd:
        Cost for completion (output) tokens.
    """

    record: TokenUsageRecord
    input_cost_usd: float
    output_cost_usd: float

    @property
    def total_cost_usd(self) -> float:
        return self.input_cost_usd + self.output_cost_usd


@dataclass
class SessionCostSummary:
    """Aggregated costs for one workflow session (MA-703).

    Attributes
    ----------
    total_usd:
        Sum of all per-call costs.
    per_agent:
        Cost keyed by agent name.
    per_stage:
        Cost keyed by workflow stage.
    per_operation:
        Cost keyed by operation type (``"chat"`` / ``"embedding"``).
    total_prompt_tokens:
        Sum of all prompt tokens in the session.
    total_completion_tokens:
        Sum of all completion tokens in the session.
    """

    total_usd: float = 0.0
    per_agent: dict[str, float] = field(default_factory=dict)
    per_stage: dict[str, float] = field(default_factory=dict)
    per_operation: dict[str, float] = field(default_factory=dict)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    disclaimer: str = ESTIMATE_DISCLAIMER


# ---------------------------------------------------------------------------
# Pricing loader
# ---------------------------------------------------------------------------


def load_pricing(path: Path = _DEFAULT_PRICING_PATH) -> dict[str, Any]:
    """Load model pricing from the external JSON configuration file (MA-702).

    Returns an empty dict if the file is missing or malformed; callers must
    handle the ``"default"`` key fallback themselves.
    """
    if not path.exists():
        log.warning(
            "Pricing file not found at %s — FinOps calculations will use zero prices.", path
        )
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        models = data.get("models", {})
        if not isinstance(models, dict):
            raise ValueError("'models' must be a JSON object")
        return models
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Could not parse pricing file %s: %s — using zero prices.", path, exc)
        return {}


# ---------------------------------------------------------------------------
# Cost tracker
# ---------------------------------------------------------------------------


@dataclass
class CostTracker:
    """Accumulate token usage and calculate FinOps estimates (MA-701, MA-703).

    Parameters
    ----------
    pricing_path:
        Path to ``pricing.json``.  Loaded once on first use.
    """

    pricing_path: Path = _DEFAULT_PRICING_PATH
    _records: list[TokenUsageRecord] = field(default_factory=list, init=False)
    _pricing: dict[str, Any] | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # Recording API
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        run_id: str,
        agent: str,
        stage: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        operation: str = "chat",
        max_tokens: int | None = None,
    ) -> TokenUsageRecord:
        """Record one API call's token usage (MA-701).

        Parameters are intentionally keyword-only to prevent silent positional
        mistakes when plumbing token counts from provider responses.
        """
        usage = TokenUsageRecord(
            run_id=run_id,
            agent=agent,
            stage=stage,
            model=model,
            prompt_tokens=max(0, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
            operation=operation,
            max_tokens=max_tokens,
        )
        self._records.append(usage)
        log.debug(
            "Token usage recorded: run=%s agent=%s stage=%s model=%s "
            "prompt=%d completion=%d op=%s",
            run_id,
            agent,
            stage,
            model,
            usage.prompt_tokens,
            usage.completion_tokens,
            operation,
        )
        return usage

    def records_for_run(self, run_id: str) -> list[TokenUsageRecord]:
        """Return all usage records for a specific run ID."""
        return [r for r in self._records if r.run_id == run_id]

    def add_record(self, record: TokenUsageRecord) -> None:
        """Add a previously persisted record unless it is already present."""
        if all(existing.record_id != record.record_id for existing in self._records):
            self._records.append(record)

    # ------------------------------------------------------------------
    # Cost calculation
    # ------------------------------------------------------------------

    def calculate_cost(self, record: TokenUsageRecord) -> CostBreakdown:
        """Return a :class:`CostBreakdown` for one usage record (MA-703)."""
        pricing = self._get_pricing()
        model_prices = pricing.get(record.model) or pricing.get("default") or {}

        input_rate = float(model_prices.get("input_per_1k_tokens", 0.0))
        output_rate = float(model_prices.get("output_per_1k_tokens", 0.0))

        if not model_prices:
            log.warning(
                "No pricing found for model '%s' and no 'default' fallback — "
                "cost will be reported as $0.00.",
                record.model,
            )

        return CostBreakdown(
            record=record,
            input_cost_usd=record.prompt_tokens * input_rate / 1000.0,
            output_cost_usd=record.completion_tokens * output_rate / 1000.0,
        )

    def session_summary(
        self,
        run_id: str,
        records: Iterable[TokenUsageRecord] | None = None,
    ) -> SessionCostSummary:
        """Aggregate all costs for a run into a :class:`SessionCostSummary` (MA-703)."""
        selected_records = (
            self.records_for_run(run_id)
            if records is None
            else [record for record in records if record.run_id == run_id]
        )
        summary = SessionCostSummary()

        for record in selected_records:
            breakdown = self.calculate_cost(record)
            cost = breakdown.total_cost_usd

            summary.total_usd += cost
            summary.per_agent[record.agent] = summary.per_agent.get(record.agent, 0.0) + cost
            summary.per_stage[record.stage] = summary.per_stage.get(record.stage, 0.0) + cost
            summary.per_operation[record.operation] = (
                summary.per_operation.get(record.operation, 0.0) + cost
            )
            summary.total_prompt_tokens += record.prompt_tokens
            summary.total_completion_tokens += record.completion_tokens

        # Round totals to avoid floating-point noise in display
        summary.total_usd = round(summary.total_usd, 6)
        summary.per_agent = {k: round(v, 6) for k, v in summary.per_agent.items()}
        summary.per_stage = {k: round(v, 6) for k, v in summary.per_stage.items()}
        summary.per_operation = {k: round(v, 6) for k, v in summary.per_operation.items()}
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_pricing(self) -> dict[str, Any]:
        if self._pricing is None:
            self._pricing = load_pricing(self.pricing_path)
        return self._pricing
