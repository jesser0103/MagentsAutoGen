"""Unit and integration tests for SecurityRedTeamAgent and WorkflowOrchestrator integration."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest

from src.agents.parsing import AgentOutputError
from src.agents.security_agent import SecurityRedTeamAgent, parse_red_team_report
from src.workflow.models import (
    ArtifactLanguage,
    AttackFinding,
    AttackVector,
    FindingSeverity,
    GeneratedArtifact,
    Plan,
    PlanStep,
    RedTeamReport,
    ReviewVerdict,
    RunStatus,
    WorkflowEventType,
    WorkflowRun,
)
from src.workflow.orchestrator import WorkflowOrchestrator
from src.workflow.store import FileRunStore


class FakeModelProvider:
    """Mock model provider returning preconfigured completion strings."""

    def __init__(self, response: str) -> None:
        self.response = response

    async def generate(self, name: str, instructions: str, prompt: str) -> str:
        return self.response


class FakePlanner:
    async def plan(self, user_request: str) -> Plan:
        return Plan(
            summary="Deploy infrastructure",
            steps=(PlanStep(language=ArtifactLanguage.TERRAFORM, description="Create storage"),),
        )


class FakeCoder:
    async def generate(
        self, plan: Plan, retrieved_rules: tuple[str, ...], reviewer_feedback: tuple[str, ...]
    ) -> GeneratedArtifact:
        return GeneratedArtifact(
            language=ArtifactLanguage.TERRAFORM,
            filename="main.tf",
            content='resource "azurerm_storage_account" "st" { name = "sttest" }',
        )


class FakeReviewer:
    async def review(
        self, artifact: GeneratedArtifact, findings: tuple
    ) -> tuple:
        from src.workflow.models import ReviewResult
        blocking = [f for f in findings if f.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}]
        if blocking:
            return ReviewResult(
                verdict=ReviewVerdict.REJECT,
                assessment="Security findings present",
                findings=findings,
                required_changes=tuple(f.remediation for f in blocking),
            )
        return ReviewResult(
            verdict=ReviewVerdict.APPROVE,
            assessment="All checks passed",
            findings=findings,
            required_changes=(),
        )


class FakeInputGuard:
    async def screen(self, user_request: str):
        from src.security.content_safety import SafetyDecision
        return SafetyDecision(allowed=True, reason="Clean input")


class FakeRuleRetriever:
    def search(self, query: str, limit: int = 4):
        return ()


class FakePolicyGuard:
    def scan(self, artifact: GeneratedArtifact):
        return ()


class FakeScanner:
    def scan(self, artifact: GeneratedArtifact):
        from src.workflow.models import ScanReport
        return (ScanReport(tool="tfsec", succeeded=True, findings=()),)


class FakeSandbox:
    def validate(self, artifact: GeneratedArtifact):
        from src.workflow.models import SandboxResult
        return SandboxResult(succeeded=True, summary="Sandbox passed")


class FakeRedTeam:
    """Mock red team agent returning a critical vulnerability."""

    def __init__(self, finding: AttackFinding | None = None) -> None:
        self.finding = finding or AttackFinding(
            rule_id="RT-001",
            severity=FindingSeverity.CRITICAL,
            vector=AttackVector.PRIVILEGE_ESCALATION,
            message="Wildcard Owner role assigned at subscription scope.",
            remediation="Restrict role assignment scope to resource group.",
            exploit_scenario="An adversary compromises the workload identity and gains full subscription access.",
        )

    async def analyze(self, artifact: GeneratedArtifact) -> RedTeamReport:
        return RedTeamReport(
            assessment="Critical privilege escalation risk detected.",
            risk_score=9.5,
            attack_findings=(self.finding,),
        )


# ---------------------------------------------------------------------------
# Test 1: Parsing tests
# ---------------------------------------------------------------------------


def test_parse_red_team_report_valid_json() -> None:
    raw_response = json.dumps(
        {
            "assessment": "High risk infrastructure deployment detected.",
            "risk_score": 8.5,
            "attack_findings": [
                {
                    "rule_id": "RT-001",
                    "severity": "critical",
                    "vector": "privilege_escalation",
                    "message": "Wildcard admin role.",
                    "remediation": "Remove wildcard.",
                    "exploit_scenario": "Gain full cluster control.",
                }
            ],
        }
    )
    report = parse_red_team_report(raw_response)
    assert report.assessment == "High risk infrastructure deployment detected."
    assert report.risk_score == 8.5
    assert len(report.attack_findings) == 1
    finding = report.attack_findings[0]
    assert finding.rule_id == "RT-001"
    assert finding.severity == FindingSeverity.CRITICAL
    assert finding.vector == AttackVector.PRIVILEGE_ESCALATION
    assert finding.message == "Wildcard admin role."


def test_parse_red_team_report_markdown_fences() -> None:
    raw_response = """```json
{
  "assessment": "Clean assessment.",
  "risk_score": 1.0,
  "attack_findings": []
}
```"""
    report = parse_red_team_report(raw_response)
    assert report.assessment == "Clean assessment."
    assert report.risk_score == 1.0
    assert len(report.attack_findings) == 0


def test_parse_red_team_report_invalid_raises_agent_output_error() -> None:
    with pytest.raises(AgentOutputError, match="Expected a JSON object"):
        parse_red_team_report("This is not JSON")

    invalid_score = json.dumps({"assessment": "Test", "risk_score": 15.0, "attack_findings": []})
    with pytest.raises(AgentOutputError, match="risk_score"):
        parse_red_team_report(invalid_score)


import asyncio

# ---------------------------------------------------------------------------
# Test 2: Orchestrator integration test asserting REJECT on CRITICAL finding
# ---------------------------------------------------------------------------


def test_orchestrator_rejects_on_critical_red_team_finding() -> None:
    async def _test() -> None:
        with TemporaryDirectory() as tmp_dir:
            run_store = FileRunStore(Path(tmp_dir))
            orchestrator = WorkflowOrchestrator(
                planner=FakePlanner(),
                coder=FakeCoder(),
                reviewer=FakeReviewer(),
                input_screen=FakeInputGuard(),
                rule_retriever=FakeRuleRetriever(),
                policy_guard=FakePolicyGuard(),
                scanner=FakeScanner(),
                sandbox=FakeSandbox(),
                run_store=run_store,
                security_red_team=FakeRedTeam(),
                max_review_rounds=1,
            )

            # 1. Submit mission
            run = await orchestrator.submit("Create Azure VM")
            assert run.status == RunStatus.AWAITING_APPROVAL

            # 2. Approve plan to trigger coding + scanning + red team + reviewing
            updated_run = await orchestrator.approve(run.run_id)

            # 3. Assert red team ran, event was recorded, and Reviewer rejected the artifact
            assert len(updated_run.red_team_reports) == 1
            assert updated_run.red_team_reports[0].risk_score == 9.5
            assert updated_run.status == RunStatus.NEEDS_MANUAL_INTERVENTION
            assert updated_run.reviews[-1].verdict == ReviewVerdict.REJECT
            assert any(e.event_type == WorkflowEventType.REDTEAM_COMPLETED.value for e in updated_run.events)

    asyncio.run(_test())


# ---------------------------------------------------------------------------
# Test 3: Serialization round-trip test for WorkflowRun with red_team_reports
# ---------------------------------------------------------------------------


def test_workflow_run_red_team_reports_store_roundtrip() -> None:
    with TemporaryDirectory() as tmp_dir:
        store = FileRunStore(Path(tmp_dir))
        run = WorkflowRun(user_request="Test Red Team Store")
        report = RedTeamReport(
            assessment="Exfiltration vulnerability found.",
            risk_score=7.8,
            attack_findings=(
                AttackFinding(
                    rule_id="RT-002",
                    severity=FindingSeverity.HIGH,
                    vector=AttackVector.DATA_EXFILTRATION,
                    message="Public storage endpoint allows unauthorized data read.",
                    remediation="Enable private endpoint.",
                    exploit_scenario="Attacker dumps blob contents via public internet.",
                ),
            ),
        )
        run.red_team_reports.append(report)
        store.save(run)

        reloaded = store.load(run.run_id)
        assert len(reloaded.red_team_reports) == 1
        reloaded_report = reloaded.red_team_reports[0]
        assert reloaded_report.assessment == "Exfiltration vulnerability found."
        assert reloaded_report.risk_score == 7.8
        assert len(reloaded_report.attack_findings) == 1
        finding = reloaded_report.attack_findings[0]
        assert finding.rule_id == "RT-002"
        assert finding.severity == FindingSeverity.HIGH
        assert finding.vector == AttackVector.DATA_EXFILTRATION
        assert finding.message == "Public storage endpoint allows unauthorized data read."
