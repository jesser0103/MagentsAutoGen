"""Coder agent that returns a single Python or Terraform artifact."""

from __future__ import annotations

from dataclasses import dataclass

from src.agents.model_provider import ModelProvider
from src.agents.parsing import AgentOutputError, extract_code_block
from src.workflow.models import ArtifactLanguage, GeneratedArtifact, Plan, SecurityFinding

# Tags that EVERY Azure resource block MUST carry (MA-402).
# Keep this list in sync with the scanner check in src/security/tag_checker.py.
REQUIRED_AZURE_TAGS: tuple[str, ...] = ("environment", "owner", "cost_center")

CODER_INSTRUCTIONS = """
You are the Coder agent for MagentAutoGen. Implement only the approved plan and the
retrieved internal policies. Do not execute code, use shell commands, fabricate secrets,
or add unrelated features. Generate either one Python artifact or one Terraform artifact.
For Azure resources, use least-privilege RBAC, encryption, HTTPS-only settings, no public
exposure, and environment, owner, and cost_center tags. Reference Key Vault rather than
hardcoding secrets. Python Azure automation must use DefaultAzureCredential and supported Azure
SDK libraries rather than Azure CLI commands. Return exactly one fenced Python or Terraform code
block and no prose.

MANDATORY TAG REQUIREMENT (MA-402): Every Terraform resource block that creates an Azure
resource MUST include a tags block containing ALL of the following keys:
  - environment  (e.g. "dev", "staging", "prod")
  - owner        (e.g. the team or service name)
  - cost_center  (e.g. the cost-centre code)

Example:
  tags = {
    environment = var.environment
    owner       = var.owner
    cost_center = var.cost_center
  }

Omitting any of these tags is a CRITICAL policy violation and WILL cause the security
review to fail.  Do not omit them under any circumstances.
""".strip()


@dataclass
class CoderAgent:
    provider: ModelProvider
    name: str = "coder"

    async def generate(
        self,
        plan: Plan,
        retrieved_rules: tuple[str, ...],
        reviewer_feedback: tuple[str, ...] = (),
        scanner_findings: tuple[SecurityFinding, ...] = (),
    ) -> GeneratedArtifact:
        language = _plan_language(plan)
        prompt = _build_prompt(
            plan,
            retrieved_rules,
            reviewer_feedback,
            scanner_findings,
            language,
        )
        response = await self.provider.generate(self.name, CODER_INSTRUCTIONS, prompt)
        generated_language, code = extract_code_block(response)
        if generated_language != language:
            raise AgentOutputError(
                "Coder returned "
                f"{generated_language.value} but the approved plan requires {language.value}"
            )
        filename = "main.py" if language is ArtifactLanguage.PYTHON else "main.tf"
        return GeneratedArtifact(language=language, filename=filename, content=code)


def _plan_language(plan: Plan) -> ArtifactLanguage:
    languages = {step.language for step in plan.steps}
    if len(languages) != 1:
        raise AgentOutputError(
            "The first delivery supports one artifact language per approved plan"
        )
    return languages.pop()


def _build_prompt(
    plan: Plan,
    retrieved_rules: tuple[str, ...],
    reviewer_feedback: tuple[str, ...],
    scanner_findings: tuple[SecurityFinding, ...],
    language: ArtifactLanguage,
) -> str:
    steps = "\n".join(f"- {step.description}" for step in plan.steps)
    rules = "\n".join(f"- {rule}" for rule in retrieved_rules) or "- No relevant policy matched."
    feedback = "\n".join(f"- {item}" for item in reviewer_feedback) or "- No prior review feedback."
    scanner_evidence = "\n".join(
        _scanner_finding_summary(finding) for finding in scanner_findings
    ) or "- No scanner findings require correction."
    return (
        f"Approved plan summary: {plan.summary}\n"
        f"Required language: {language.value}\n"
        f"Approved steps:\n{steps}\n"
        f"Retrieved policies:\n{rules}\n"
        f"Reviewer feedback to address:\n{feedback}\n"
        f"Scanner findings to correct before resubmission:\n{scanner_evidence}"
    )


def _scanner_finding_summary(finding: SecurityFinding) -> str:
    """Preserve scanner rule IDs and locations in the Coder's repair context."""
    location = f" at {finding.location}" if finding.location else ""
    evidence = f" Evidence: {finding.evidence}" if finding.evidence else ""
    return (
        f"- [{finding.severity.value}] {finding.tool}/{finding.rule_id}{location}: "
        f"{finding.message}. Required remediation: {finding.remediation}.{evidence}"
    )
