"""Cloud-security reviewer with model output constrained by policy findings."""

from __future__ import annotations

from dataclasses import dataclass

from src.agents.model_provider import ModelProvider
from src.agents.parsing import AgentOutputError, parse_json_object
from src.workflow.models import (
    FindingSeverity,
    GeneratedArtifact,
    ReviewResult,
    ReviewVerdict,
    SecurityFinding,
)

REVIEWER_INSTRUCTIONS = """
You are the Reviewer agent for MagentAutoGen and act as a Cloud Security Architect.
Review the generated artifact and the supplied scanner evidence. Do not approve code with
critical or high security findings. Require encryption, HTTPS-only access, no public exposure,
no plaintext secrets, least-privilege RBAC, and environment/owner/cost_center tags where
applicable. Return exactly one JSON object with this schema:
{
  "verdict": "approve|reject",
  "assessment": "short evidence-based review",
  "required_changes": ["specific change"]
}
""".strip()


@dataclass
class ReviewerAgent:
    provider: ModelProvider
    name: str = "reviewer"

    async def review(
        self,
        artifact: GeneratedArtifact,
        findings: tuple[SecurityFinding, ...],
    ) -> ReviewResult:
        blocking_findings = tuple(
            finding
            for finding in findings
            if finding.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}
        )
        if blocking_findings:
            changes = tuple(finding.remediation for finding in blocking_findings)
            return ReviewResult(
                verdict=ReviewVerdict.REJECT,
                assessment="Local policy guard found blocking security violations.",
                findings=findings,
                required_changes=changes,
            )

        prompt = _build_prompt(artifact, findings)
        response = await self.provider.generate(self.name, REVIEWER_INSTRUCTIONS, prompt)
        return _parse_review(response, findings)


def _build_prompt(artifact: GeneratedArtifact, findings: tuple[SecurityFinding, ...]) -> str:
    evidence = "\n".join(
        _finding_summary(finding) for finding in findings
    ) or "- No local-policy or static-analysis findings."
    return (
        f"Artifact language: {artifact.language.value}\n"
        f"Artifact filename: {artifact.filename}\n"
        f"Artifact content:\n```{artifact.language.value}\n{artifact.content}\n```\n"
        f"Local policy-guard findings:\n{evidence}"
    )


def _finding_summary(finding: SecurityFinding) -> str:
    location = f" at {finding.location}" if finding.location else ""
    return (
        f"- [{finding.severity.value}] {finding.tool}/{finding.rule_id}{location}: "
        f"{finding.message}"
    )


def _parse_review(response: str, findings: tuple[SecurityFinding, ...]) -> ReviewResult:
    payload = parse_json_object(response)
    verdict = payload.get("verdict")
    assessment = payload.get("assessment")
    required_changes = payload.get("required_changes", [])
    if verdict not in {ReviewVerdict.APPROVE.value, ReviewVerdict.REJECT.value}:
        raise AgentOutputError("Reviewer verdict must be approve or reject")
    if not isinstance(assessment, str) or not assessment.strip():
        raise AgentOutputError("Reviewer response requires a non-empty assessment")
    if not isinstance(required_changes, list) or not all(
        isinstance(change, str) for change in required_changes
    ):
        raise AgentOutputError("Reviewer required_changes must be an array of strings")
    parsed_verdict = ReviewVerdict(verdict)
    parsed_changes = tuple(change.strip() for change in required_changes if change.strip())
    if parsed_verdict is ReviewVerdict.REJECT and not parsed_changes:
        raise AgentOutputError("Rejected reviews must include at least one required change")
    return ReviewResult(
        verdict=parsed_verdict,
        assessment=assessment.strip(),
        findings=findings,
        required_changes=parsed_changes,
    )
