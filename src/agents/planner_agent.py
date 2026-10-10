"""Planner agent with a strict structured-plan contract."""

from __future__ import annotations

from dataclasses import dataclass

from src.agents.model_provider import ModelProvider
from src.agents.parsing import AgentOutputError, parse_json_object
from src.workflow.models import ArtifactLanguage, Plan, PlanStep

PLANNER_INSTRUCTIONS = """
You are the Planner agent for MagentAutoGen, an Azure cloud-consulting assistant.
Produce an implementation plan only. Never write code, execute tools, invent missing
Azure details, or approve a request. Every plan step must be Terraform or Python.
Return exactly one JSON object with this schema:
{
  "summary": "short request summary",
  "steps": [{"language": "terraform|python", "description": "actionable step"}],
  "open_questions": ["missing requirement"]
}
For Azure infrastructure requests, ask when the resource group, region, SKU, or
security-sensitive requirement is unclear. Azure resources require environment, owner,
and cost_center tags. Never plan public SSH, RDP, or storage exposure.
For Python Azure automation, plan managed identity with DefaultAzureCredential and supported
Azure SDK libraries rather than Azure CLI commands or hardcoded credentials.
""".strip()


@dataclass
class PlannerAgent:
    provider: ModelProvider
    name: str = "planner"

    async def plan(self, user_request: str) -> Plan:
        prompt = f"Create a safe implementation plan for this user request:\n{user_request}"
        response = await self.provider.generate(self.name, PLANNER_INSTRUCTIONS, prompt)
        return _parse_plan(response)


def _parse_plan(response: str) -> Plan:
    payload = parse_json_object(response)
    summary = payload.get("summary")
    raw_steps = payload.get("steps")
    raw_questions = payload.get("open_questions", [])
    if not isinstance(summary, str) or not summary.strip():
        raise AgentOutputError("Planner response requires a non-empty summary")
    if not isinstance(raw_steps, list):
        raise AgentOutputError("Planner response requires a steps array")
    if not isinstance(raw_questions, list) or not all(
        isinstance(question, str) for question in raw_questions
    ):
        raise AgentOutputError("Planner open_questions must be an array of strings")

    steps = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            raise AgentOutputError("Each plan step must be an object")
        language = raw_step.get("language")
        description = raw_step.get("description")
        if (
            not isinstance(language, str)
            or not isinstance(description, str)
            or not description.strip()
        ):
            raise AgentOutputError("Each plan step needs language and description")
        try:
            steps.append(
                PlanStep(
                    language=ArtifactLanguage(language.lower()),
                    description=description,
                )
            )
        except ValueError as error:
            raise AgentOutputError(f"Unsupported plan language: {language}") from error

    return Plan(
        summary=summary.strip(),
        steps=tuple(steps),
        open_questions=tuple(question.strip() for question in raw_questions if question.strip()),
    )
