"""FinOps Agent — GPT-4o powered Azure cloud cost estimator.

Evaluates generated Terraform / Bicep / Python IaC artifacts and produces
a structured :class:`FinOpsReport` containing:

* Estimated monthly cloud OpEx per resource type (USD).
* SKU-specific cost drivers.
* Actionable right-sizing recommendations (reserved instances, tier downgrades,
  lifecycle rules, etc.).

The agent is designed to run *after* the Coder generates an artifact and
*before* the Reviewer signs off, giving the operator a cost envelope alongside
the security posture before human approval is re-requested.

It is intentionally non-blocking: a failed FinOps call produces an empty report
with a warning rather than failing the entire workflow.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

from src.workflow.models import (
    FinOpsCostDriver,
    FinOpsReport,
    GeneratedArtifact,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an Azure FinOps specialist embedded in an
AI-powered infrastructure governance platform.

Your job is to review generated Terraform / Bicep / Python infrastructure
code and produce a concise but accurate cloud cost projection.

Rules:
1. Respond ONLY with a single valid JSON object — no markdown fences, no prose.
2. Use current Azure public pricing (East US region by default).
3. Flag every resource type you recognise: VMs, Storage Accounts, Key Vaults,
   Service Bus, PostgreSQL, Container Apps, OpenAI, etc.
4. If you cannot determine a SKU, make a conservative worst-case estimate and
   note it in "notes".
5. Always provide at least one actionable cost-optimisation recommendation.

JSON schema (strict):
{
  "total_monthly_usd": <number>,
  "currency": "USD",
  "cost_drivers": [
    {
      "resource_type": "<string>",
      "estimated_monthly_usd": <number>,
      "sku": "<string>",
      "notes": "<string>"
    }
  ],
  "recommendations": ["<string>", ...],
  "raw_assessment": "<brief free-text summary>"
}"""

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class ModelProvider(Protocol):
    async def complete(self, system: str, user: str) -> str:
        """Return the model completion text for the given prompt."""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


@dataclass
class FinOpsAgent:
    """Estimates monthly Azure cloud cost from a generated IaC artifact.

    Parameters
    ----------
    provider:
        Any object satisfying the :class:`ModelProvider` protocol
        (``AgentFrameworkProvider`` or ``DemoModelProvider``).
    """

    provider: ModelProvider

    async def estimate(self, artifact: GeneratedArtifact) -> FinOpsReport:
        """Return a :class:`FinOpsReport` for *artifact*.

        Never raises — failures produce a zero-cost report with a warning event
        so the downstream workflow is not blocked.
        """
        try:
            return await self._run_estimation(artifact)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "FinOps estimation failed — returning empty report. error=%s", exc
            )
            return FinOpsReport(
                total_monthly_usd=0.0,
                currency="USD",
                cost_drivers=(),
                recommendations=(
                    "FinOps estimation unavailable — review manually before deployment.",
                ),
                raw_assessment=f"Estimation failed: {exc}",
            )

    async def _run_estimation(self, artifact: GeneratedArtifact) -> FinOpsReport:
        user_prompt = (
            f"Artifact filename: {artifact.filename}\n"
            f"Language: {artifact.language.value}\n\n"
            f"```{artifact.language.value}\n{artifact.content}\n```\n\n"
            "Estimate the monthly Azure cloud cost for this infrastructure."
        )
        raw = await self.provider.complete(_SYSTEM_PROMPT, user_prompt)
        return _parse_report(raw)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_report(raw: str) -> FinOpsReport:
    """Parse the model output into a :class:`FinOpsReport`.

    Accepts both clean JSON and JSON embedded inside markdown code fences.
    """
    text = raw.strip()
    # Strip optional markdown fences (```json … ```)
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence:
        text = fence.group(1).strip()

    data: dict = json.loads(text)

    drivers = tuple(
        FinOpsCostDriver(
            resource_type=str(d["resource_type"]),
            estimated_monthly_usd=float(d["estimated_monthly_usd"]),
            sku=str(d.get("sku", "unknown")),
            notes=str(d.get("notes", "")),
        )
        for d in data.get("cost_drivers", [])
    )
    return FinOpsReport(
        total_monthly_usd=float(data.get("total_monthly_usd", 0.0)),
        currency=str(data.get("currency", "USD")),
        cost_drivers=drivers,
        recommendations=tuple(str(r) for r in data.get("recommendations", [])),
        raw_assessment=str(data.get("raw_assessment", "")),
    )
