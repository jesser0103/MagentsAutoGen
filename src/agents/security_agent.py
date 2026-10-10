"""Security Red Team Agent — Adversarial cloud infrastructure penetration tester.

Performs proactive adversarial analysis on generated IaC artifacts (Terraform / Bicep / Python)
to uncover exploitable security vulnerabilities, privilege escalation vectors, and data exfiltration paths
before reviewer approval.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from src.agents.model_provider import ModelProvider
from src.agents.parsing import AgentOutputError, parse_json_object
from src.workflow.models import (
    AttackFinding,
    AttackVector,
    FindingSeverity,
    GeneratedArtifact,
    RedTeamReport,
)

log = logging.getLogger(__name__)

RED_TEAM_INSTRUCTIONS = """
You are the Security Red Team Agent for MagentAutoGen, operating as an elite Cloud Penetration Tester and Adversarial Security Specialist.

Your objective is to proactively attack, exploit, and find architectural vulnerabilities in the generated cloud infrastructure artifact.
Focus on real-world attack chains and offensive vectors:
1. **Privilege Escalation:** Wildcard IAM permissions (`*`), excessive subscription-scope Contributor/Owner assignments, missing credential boundaries.
2. **Data Exfiltration:** Public endpoints on storage/databases, cross-tenant replication, lack of egress filtering.
3. **Network Perimeter Leaks:** Permissive CIDRs (`0.0.0.0/0`) on management ports (22, 3389, 5985), unattached NSGs, missing Bastion.
4. **Secret Exposure:** Hardcoded credentials, plain-text connection strings, unmanaged environment variable secrets.
5. **Supply Chain Risks:** Unpinned provider/module versions, third-party unauthenticated registry dependencies.
6. **Unencrypted State:** Missing storage encryption, missing Key Vault HSM wrapping.

Return ONLY a single valid JSON object adhering to this schema:
{
  "assessment": "Brief executive adversarial assessment summarizing the attack surface.",
  "risk_score": <number between 0.0 (fully secure) and 10.0 (critical exploitability)>,
  "attack_findings": [
    {
      "rule_id": "RT-001",
      "severity": "critical|high|medium|low",
      "vector": "privilege_escalation|data_exfiltration|network_perimeter_leak|supply_chain_dependency|secret_exposure|unencrypted_state|other",
      "message": "Detailed description of the exploit vector.",
      "remediation": "Concrete actionable remediation.",
      "exploit_scenario": "Step-by-step offensive attack scenario an adversary would execute."
    }
  ]
}
""".strip()


class SecurityRedTeam(Protocol):
    """Protocol for adversarial security analysis agents."""

    async def analyze(self, artifact: GeneratedArtifact) -> RedTeamReport:
        """Analyze *artifact* and return an adversarial :class:`RedTeamReport`."""


@dataclass
class SecurityRedTeamAgent:
    """Adversarial security agent that attempts to identify exploitable attack vectors in IaC code.

    Parameters
    ----------
    provider:
        Any provider implementing the :class:`ModelProvider` protocol.
    name:
        Agent identifier string for logs and telemetry (default: "security_red_team").
    """

    provider: ModelProvider
    name: str = "security_red_team"

    async def analyze(self, artifact: GeneratedArtifact) -> RedTeamReport:
        """Perform adversarial penetration analysis on the generated *artifact*.

        Falls back gracefully with an empty report on unhandled provider exceptions to avoid
        halting non-critical pipeline executions when telemetry/network drops.
        """
        try:
            prompt = _build_attack_prompt(artifact)
            response = await self.provider.generate(self.name, RED_TEAM_INSTRUCTIONS, prompt)
            return parse_red_team_report(response)
        except AgentOutputError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("Security Red Team analysis encountered an exception: %s", exc)
            return RedTeamReport(
                assessment=f"Red team analysis unavailable: {exc}",
                risk_score=0.0,
                attack_findings=(),
            )


def parse_red_team_report(response: str) -> RedTeamReport:
    """Parse and validate a model response into a strongly-typed :class:`RedTeamReport`.

    Reuses :func:`parse_json_object` from ``src.agents.parsing`` to handle both raw JSON
    and Markdown-fenced responses. Raises :class:`AgentOutputError` on contract violations.
    """
    payload = parse_json_object(response)

    assessment = payload.get("assessment")
    if not isinstance(assessment, str) or not assessment.strip():
        raise AgentOutputError("Red Team report requires a non-empty 'assessment' string")

    raw_risk_score = payload.get("risk_score", 0.0)
    try:
        risk_score = float(raw_risk_score)
        if not (0.0 <= risk_score <= 10.0):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise AgentOutputError("Red Team 'risk_score' must be a float between 0.0 and 10.0") from exc

    raw_findings = payload.get("attack_findings", [])
    if not isinstance(raw_findings, list):
        raise AgentOutputError("Red Team 'attack_findings' must be an array")

    findings = []
    for idx, raw_item in enumerate(raw_findings):
        if not isinstance(raw_item, dict):
            raise AgentOutputError(f"Attack finding at index {idx} must be a JSON object")

        rule_id = str(raw_item.get("rule_id", f"RT-{idx+1:03d}"))
        raw_severity = str(raw_item.get("severity", "medium")).lower()
        try:
            severity = FindingSeverity(raw_severity)
        except ValueError as exc:
            raise AgentOutputError(f"Invalid severity '{raw_severity}' in attack finding {rule_id}") from exc

        raw_vector = str(raw_item.get("vector", "other")).lower()
        try:
            vector = AttackVector(raw_vector)
        except ValueError:
            vector = AttackVector.OTHER

        message = raw_item.get("message")
        if not isinstance(message, str) or not message.strip():
            raise AgentOutputError(f"Attack finding {rule_id} requires a non-empty 'message'")

        remediation = raw_item.get("remediation")
        if not isinstance(remediation, str) or not remediation.strip():
            raise AgentOutputError(f"Attack finding {rule_id} requires a non-empty 'remediation'")

        exploit_scenario = str(raw_item.get("exploit_scenario") or "")

        findings.append(
            AttackFinding(
                rule_id=rule_id,
                severity=severity,
                vector=vector,
                message=message.strip(),
                remediation=remediation.strip(),
                exploit_scenario=exploit_scenario.strip(),
            )
        )

    return RedTeamReport(
        assessment=assessment.strip(),
        risk_score=round(risk_score, 1),
        attack_findings=tuple(findings),
    )


def _build_attack_prompt(artifact: GeneratedArtifact) -> str:
    return (
        f"Artifact filename: {artifact.filename}\n"
        f"Language: {artifact.language.value}\n\n"
        f"```{artifact.language.value}\n"
        f"{artifact.content}\n"
        f"```\n\n"
        "Execute adversarial attack simulation on this infrastructure artifact."
    )
