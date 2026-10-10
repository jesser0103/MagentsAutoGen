"""Approval-gated Planner, Coder, and Reviewer orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Protocol

from src.agents.finops_agent import FinOpsAgent
from src.agents.model_provider import model_call_context
from src.agents.security_agent import SecurityRedTeam
from src.rag.vector_store import RetrievedPolicy
from src.security.content_safety import InputScreen
from src.security.local_policy import LocalPolicyGuard
from src.security.sandbox import ArtifactSandbox
from src.security.scanners import ArtifactScanner
from src.utils.context_manager import BoundedContextManager, ContextManager
from src.utils.cost_tracker import CostTracker
from src.utils.telemetry import add_span_event, workflow_span
from src.workflow.models import (
    ContextAudit,
    GeneratedArtifact,
    Plan,
    RetrievalEvidence,
    ReviewResult,
    ReviewVerdict,
    RunStatus,
    SandboxResult,
    ScanReport,
    SecurityFinding,
    WorkflowEventType,
    WorkflowRun,
)
from src.workflow.store import RunStore

log = logging.getLogger(__name__)


class WorkflowStateError(RuntimeError):
    """Raised when an operator requests an invalid workflow action."""


class Planner(Protocol):
    async def plan(self, user_request: str) -> Plan:
        """Create a plan for the user request."""


class Coder(Protocol):
    async def generate(
        self,
        plan: Plan,
        retrieved_rules: tuple[str, ...],
        reviewer_feedback: tuple[str, ...],
        scanner_findings: tuple[SecurityFinding, ...] = (),
    ) -> GeneratedArtifact:
        """Generate one code artifact."""


class Reviewer(Protocol):
    async def review(
        self,
        artifact: GeneratedArtifact,
        findings: tuple[SecurityFinding, ...],
    ) -> ReviewResult:
        """Review one generated code artifact."""


class RuleRetriever(Protocol):
    def search(self, query: str, limit: int = 4) -> tuple[RetrievedPolicy, ...]:
        """Return relevant internal policy rules and relevance evidence."""


@dataclass
class WorkflowOrchestrator:
    planner: Planner
    coder: Coder
    reviewer: Reviewer
    input_screen: InputScreen
    rule_retriever: RuleRetriever
    policy_guard: LocalPolicyGuard
    scanner: ArtifactScanner
    sandbox: ArtifactSandbox
    run_store: RunStore
    context_manager: ContextManager = field(default_factory=BoundedContextManager)
    cost_tracker: CostTracker = field(default_factory=CostTracker)
    finops_agent: FinOpsAgent | None = None
    security_red_team: SecurityRedTeam | None = None
    max_review_rounds: int = 5
    max_auto_fix_attempts: int = 2

    async def submit(self, user_request: str) -> WorkflowRun:
        run = WorkflowRun(user_request=user_request.strip())
        with workflow_span("workflow.submit", run.run_id):
            log.info(
                "Workflow submission started",
                extra={"event_type": "workflow_started", "operation": "submit"},
            )
            with workflow_span("workflow.input_screen", run.run_id):
                decision = await self.input_screen.screen(run.user_request)
            run.add_event(WorkflowEventType.INPUT_SCREENED, "input_guard", decision.reason)
            if not decision.allowed:
                run.transition(
                    RunStatus.BLOCKED,
                    "input_guard",
                    "Request blocked before planning.",
                )
                self._save(run)
                return run
            return await self._plan(run)

    async def clarify(self, run_id: str, clarification: str) -> WorkflowRun:
        run = self.run_store.load(run_id)
        with workflow_span("workflow.clarify", run.run_id):
            if run.status not in {
                RunStatus.NEEDS_CLARIFICATION,
                RunStatus.AWAITING_APPROVAL,
            }:
                raise WorkflowStateError(
                    "Only a plan awaiting clarification or approval can be revised"
                )
            if not clarification.strip():
                raise WorkflowStateError("Clarification cannot be empty")
            run.user_request = (
                f"{run.user_request}\n\nOperator clarification: {clarification.strip()}"
            )
            return await self._plan(run)

    def get_run(self, run_id: str) -> WorkflowRun:
        """Retrieve a persisted workflow run by its ID."""
        return self.run_store.load(run_id)

    def delete_run(self, run_id: str) -> None:
        """Delete a persisted workflow run by its ID."""
        self.run_store.delete(run_id)

    async def reject(self, run_id: str, feedback: str) -> WorkflowRun:
        """Reject an awaiting-approval plan and return a revised plan (MA-303).

        The operator's rejection feedback is appended to the user request and
        the Planner is re-invoked so the revised plan incorporates the operator's
        concerns.  Only runs in the ``AWAITING_APPROVAL`` state can be rejected.

        Parameters
        ----------
        run_id:
            ID of the run whose plan is being rejected.
        feedback:
            The operator's reason for rejection.  Must be non-empty so the
            Planner has actionable context for the revision.
        """
        run = self.run_store.load(run_id)
        with workflow_span("workflow.reject", run.run_id):
            if run.status is not RunStatus.AWAITING_APPROVAL:
                raise WorkflowStateError(
                    "Only a plan that is awaiting approval can be rejected"
                )
            if not feedback.strip():
                raise WorkflowStateError("Rejection feedback cannot be empty")
            run.user_request = (
                f"{run.user_request}\n\n"
                f"Operator rejected the plan with feedback: {feedback.strip()}"
            )
            return await self._plan(run)

    def update_plan(self, run_id: str, plan: Plan) -> WorkflowRun:
        """Persist an operator-edited plan before the approval gate is opened."""
        run = self.run_store.load(run_id)
        if run.status is not RunStatus.AWAITING_APPROVAL:
            raise WorkflowStateError("Only a plan awaiting approval can be edited")
        if not plan.ready_for_approval:
            raise WorkflowStateError(
                "An edited plan requires a summary and at least one complete step"
            )

        run.plan = plan
        run.add_event(
            WorkflowEventType.PLAN_UPDATED,
            "human",
            "Operator updated the execution plan before approval.",
        )
        self._save(run)
        return run

    async def approve(self, run_id: str) -> WorkflowRun:
        run = self.run_store.load(run_id)
        with workflow_span("workflow.approve", run.run_id):
            return await self._approve(run)

    async def _approve(self, run: WorkflowRun) -> WorkflowRun:
        if run.status is not RunStatus.AWAITING_APPROVAL or not run.plan:
            raise WorkflowStateError("Only an approved-ready plan can start coding")
        run.transition(RunStatus.CODING, "human", "Operator approved the implementation plan.")
        self._save(run)

        reviewer_feedback: tuple[str, ...] = ()
        scanner_findings: tuple[SecurityFinding, ...] = ()
        review_round = 0
        generation_attempt = 0
        while True:
            generation_attempt += 1
            round_attributes = {
                "workflow.generation_attempt": generation_attempt,
                "workflow.review_round": review_round + 1,
            }
            with workflow_span("workflow.coding", run.run_id, round_attributes):
                stage = (
                    RunStatus.AUTO_FIXING.value
                    if scanner_findings
                    else RunStatus.CODING.value
                )
                with model_call_context(run.run_id, stage):
                    if scanner_findings:
                        artifact = await self.coder.generate(
                            run.plan,
                            run.retrieved_rules,
                            reviewer_feedback,
                            scanner_findings,
                        )
                    else:
                        # Existing integrations that have not opted into auto-fixing
                        # continue to satisfy the original three-argument contract.
                        artifact = await self.coder.generate(
                            run.plan,
                            run.retrieved_rules,
                            reviewer_feedback,
                        )
            run.artifacts.append(artifact)
            run.add_event(
                WorkflowEventType.ARTIFACT_GENERATED,
                "coder",
                f"Generated {artifact.filename} for attempt {generation_attempt}.",
            )

            # ----------------------------------------------------------------
            # FinOps cost estimation (non-blocking)
            # ----------------------------------------------------------------
            if self.finops_agent is not None:
                with workflow_span("workflow.finops", run.run_id, round_attributes):
                    finops_report = await self.finops_agent.estimate(artifact)
                run.finops_reports.append(finops_report)
                run.add_event(
                    WorkflowEventType.FINOPS_COMPLETED,
                    "finops",
                    (
                        f"Estimated monthly cost: "
                        f"${finops_report.total_monthly_usd:.2f} {finops_report.currency}. "
                        f"{len(finops_report.cost_drivers)} cost driver(s) identified."
                    ),
                )
            self._save(run)
            run.transition(
                RunStatus.SCANNING,
                "scanner",
                f"Static scan round {review_round} started.",
            )
            with workflow_span("workflow.scanning", run.run_id, round_attributes):
                reports = self.scanner.scan(artifact)
            run.scans.extend(reports)
            run.add_event(
                WorkflowEventType.SCAN_COMPLETED,
                "scanner",
                _scan_summary(reports),
            )
            if any(not report.succeeded for report in reports):
                run.transition(
                    RunStatus.NEEDS_MANUAL_INTERVENTION,
                    "scanner",
                    "A required scanner did not complete. Docker validation was not started.",
                )
                self._save(run)
                return run

            scanner_findings = _scanner_findings(reports)
            if scanner_findings:
                if run.auto_fix_attempts >= self.max_auto_fix_attempts:
                    run.transition(
                        RunStatus.NEEDS_MANUAL_INTERVENTION,
                        "scanner",
                        (
                            "Scanner findings persisted after "
                            f"{self.max_auto_fix_attempts} automatic correction attempt(s)."
                        ),
                    )
                    self._save(run)
                    return run

                run.auto_fix_attempts += 1
                reviewer_feedback = ()
                run.transition(
                    RunStatus.AUTO_FIXING,
                    "scanner",
                    (
                        f"Scanner found {len(scanner_findings)} violation(s); starting automatic "
                        f"correction {run.auto_fix_attempts}/{self.max_auto_fix_attempts}."
                    ),
                )
                run.add_event(
                    WorkflowEventType.AUTO_FIX_STARTED,
                    "scanner",
                    _auto_fix_summary(
                        scanner_findings,
                        run.auto_fix_attempts,
                        self.max_auto_fix_attempts,
                    ),
                )
                self._save(run)
                continue

            # ----------------------------------------------------------------
            # Security Red Team adversarial analysis
            # ----------------------------------------------------------------
            red_team_findings: tuple[SecurityFinding, ...] = ()
            if self.security_red_team is not None:
                with workflow_span("workflow.red_team", run.run_id, round_attributes):
                    red_team_report = await self.security_red_team.analyze(artifact)
                run.red_team_reports.append(red_team_report)
                run.add_event(
                    WorkflowEventType.REDTEAM_COMPLETED,
                    "red_team",
                    (
                        "Adversarial analysis: risk score "
                        f"{red_team_report.risk_score:.1f}/10 with "
                        f"{len(red_team_report.attack_findings)} attack finding(s)."
                    ),
                )
                red_team_findings = tuple(
                    f.to_security_finding() for f in red_team_report.attack_findings
                )
            self._save(run)

            findings = (
                self.policy_guard.scan(artifact)
                + red_team_findings
            )
            scanner_findings = ()
            review_round += 1
            run.transition(RunStatus.REVIEWING, "reviewer", f"Review round {review_round} started.")
            with workflow_span("workflow.reviewing", run.run_id, round_attributes):
                with model_call_context(run.run_id, RunStatus.REVIEWING.value):
                    review = await self.reviewer.review(artifact, findings)
            run.reviews.append(review)
            run.add_event(
                WorkflowEventType.REVIEW_COMPLETED,
                "reviewer",
                f"Reviewer verdict: {review.verdict.value}.",
            )
            if review.verdict is ReviewVerdict.APPROVE:
                run.transition(
                    RunStatus.APPROVED,
                    "reviewer",
                    "Artifact approved after local policy and static-analysis checks.",
                )
                run.transition(
                    RunStatus.SANDBOXING,
                    "sandbox",
                    "Docker-only validation started after reviewer approval.",
                )
                with workflow_span("workflow.sandboxing", run.run_id, round_attributes):
                    sandbox_result = self.sandbox.validate(artifact)
                run.sandbox_results.append(sandbox_result)
                run.add_event(
                    WorkflowEventType.SANDBOX_COMPLETED,
                    "sandbox",
                    sandbox_result.summary,
                )
                self._record_infracost_breakdown(run, sandbox_result)
                if sandbox_result.succeeded:
                    run.transition(
                        RunStatus.COMPLETED,
                        "workflow",
                        "Artifact completed static review and Docker validation.",
                    )
                else:
                    run.transition(
                        RunStatus.NEEDS_MANUAL_INTERVENTION,
                        "sandbox",
                        "Docker validation failed or is unavailable. Host execution was not used.",
                    )
                self._save(run)
                return run
            if review_round >= self.max_review_rounds:
                run.transition(
                    RunStatus.NEEDS_MANUAL_INTERVENTION,
                    "workflow",
                    "Review iteration limit reached without approval.",
                )
                self._save(run)
                return run
            reviewer_feedback = review.required_changes
            run.transition(
                RunStatus.CODING,
                "coder",
                "Coder revising artifact from reviewer feedback.",
            )
            self._save(run)

    @staticmethod
    def _record_infracost_breakdown(
        run: WorkflowRun,
        sandbox_result: SandboxResult,
    ) -> None:
        """Attach sandbox-produced Terraform pricing to the matching FinOps report."""
        breakdown = sandbox_result.infracost_breakdown
        if breakdown is None:
            return
        if run.finops_reports:
            run.finops_reports[-1] = replace(
                run.finops_reports[-1],
                infracost_breakdown=breakdown,
            )
        run.add_event(
            WorkflowEventType.FINOPS_COMPLETED,
            "infracost",
            (
                f"Infracost monthly estimate: ${breakdown.total_monthly_usd:.2f} "
                f"{breakdown.currency} across {len(breakdown.resources)} resource(s)."
                if breakdown.error is None
                else f"Infracost estimate unavailable: {breakdown.error}"
            ),
        )

    def list_runs(self, limit: int = 20) -> tuple[WorkflowRun, ...]:
        """Return recent persisted runs for the frontend history panel."""
        return self.run_store.list_recent(limit)

    async def _plan(self, run: WorkflowRun) -> WorkflowRun:
        run.transition(RunStatus.PLANNING, "planner", "Planner started the request analysis.")
        context = self.context_manager.prepare(run.user_request)
        if context.truncated:
            audit = ContextAudit(
                original_characters=context.original_characters,
                sent_characters=len(context.content),
                omitted_characters=context.omitted_characters,
                omitted_sha256=context.omitted_sha256,
            )
            run.context_audits.append(audit)
            run.add_event(
                WorkflowEventType.CONTEXT_BOUNDED,
                "context_manager",
                (
                    f"Omitted {audit.omitted_characters} characters from the Planner prompt "
                    f"(sha256={audit.omitted_sha256})."
                ),
            )
        with workflow_span("workflow.planning", run.run_id):
            with model_call_context(run.run_id, RunStatus.PLANNING.value):
                plan = await self.planner.plan(context.content)
        run.plan = plan
        if plan.ready_for_approval:
            with workflow_span("workflow.policy_retrieval", run.run_id):
                retrieved = self.rule_retriever.search(run.user_request)
            run.retrieved_rules = tuple(result.rule.content for result in retrieved)
            run.retrieval_evidence = tuple(
                RetrievalEvidence(
                    rule_id=result.rule.rule_id,
                    source=result.rule.source,
                    source_hash=result.rule.source_hash,
                    score=result.score,
                )
                for result in retrieved
            )
            run.add_event(
                WorkflowEventType.RULES_RETRIEVED,
                "rag",
                _retrieval_summary(retrieved),
            )
            run.transition(
                RunStatus.AWAITING_APPROVAL,
                "planner",
                "Plan is ready and requires explicit operator approval.",
            )
        else:
            run.transition(
                RunStatus.NEEDS_CLARIFICATION,
                "planner",
                "Planner requires answers before code can be generated.",
            )
        self._save(run)
        return run

    def _save(self, run: WorkflowRun) -> None:
        """Merge newly captured usage into the persisted workflow snapshot."""
        records_by_id = {record.record_id: record for record in run.token_usage}
        for record in self.cost_tracker.records_for_run(run.run_id):
            records_by_id[record.record_id] = record
        run.token_usage = sorted(records_by_id.values(), key=lambda record: record.created_at)
        self.run_store.save(run)
        add_span_event(
            "workflow.checkpoint_saved",
            {
                "workflow.status": run.status.value,
                "workflow.token_usage_records": len(run.token_usage),
            },
        )
        log.info(
            "Workflow checkpoint saved",
            extra={
                "event_type": "checkpoint_saved",
                "operation": "persist",
                "status": run.status.value,
            },
        )


def _scanner_findings(reports: tuple[ScanReport, ...]) -> tuple[SecurityFinding, ...]:
    return tuple(finding for report in reports for finding in report.findings)


def _scan_summary(reports: tuple[ScanReport, ...]) -> str:
    completed = sum(report.succeeded for report in reports)
    findings = sum(len(report.findings) for report in reports)
    return (
        f"Completed {completed}/{len(reports)} required scanner(s) "
        f"with {findings} normalized finding(s)."
    )


def _auto_fix_summary(
    findings: tuple[SecurityFinding, ...],
    attempt: int,
    maximum: int,
) -> str:
    """Compact, auditable repair context without exposing full generated code."""
    details = "; ".join(
        f"{finding.tool}/{finding.rule_id}"
        f"{f' at {finding.location}' if finding.location else ''}"
        for finding in findings
    )
    return f"Automatic correction {attempt}/{maximum} started for: {details}."


def _retrieval_summary(retrieved: tuple[RetrievedPolicy, ...]) -> str:
    if not retrieved:
        return "No policy rules met the configured relevance threshold."
    evidence = ", ".join(f"{item.rule.rule_id} ({item.score:.2f})" for item in retrieved)
    return f"Retrieved {len(retrieved)} policy rule(s): {evidence}."
