"""Typed workflow contracts shared by the offline and Azure-backed implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from src.utils.cost_tracker import TokenUsageRecord


class ArtifactLanguage(str, Enum):
    PYTHON = "python"
    TERRAFORM = "terraform"


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewVerdict(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class RunStatus(str, Enum):
    SUBMITTED = "submitted"
    BLOCKED = "blocked"
    PLANNING = "planning"
    NEEDS_CLARIFICATION = "needs_clarification"
    AWAITING_APPROVAL = "awaiting_approval"
    CODING = "coding"
    AUTO_FIXING = "auto_fixing"
    SCANNING = "scanning"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    SANDBOXING = "sandboxing"
    COMPLETED = "completed"
    NEEDS_MANUAL_INTERVENTION = "needs_manual_intervention"
    FAILED = "failed"


WORKFLOW_EVENT_SCHEMA_VERSION = 1


class WorkflowEventType(str, Enum):
    """Non-transition events persisted with the current event schema."""

    INPUT_SCREENED = "input_screened"
    CONTEXT_BOUNDED = "context_bounded"
    RULES_RETRIEVED = "rules_retrieved"
    PLAN_UPDATED = "plan_updated"
    ARTIFACT_GENERATED = "artifact_generated"
    AUTO_FIX_STARTED = "auto_fix_started"
    SCAN_COMPLETED = "scan_completed"
    REVIEW_COMPLETED = "review_completed"
    SANDBOX_COMPLETED = "sandbox_completed"
    FINOPS_COMPLETED = "finops_completed"
    REDTEAM_COMPLETED = "redteam_completed"


@dataclass(frozen=True)
class PlanStep:
    language: ArtifactLanguage
    description: str

    def to_dict(self) -> dict[str, str]:
        return {"language": self.language.value, "description": self.description}

    @classmethod
    def from_dict(cls, value: dict[str, str]) -> "PlanStep":
        return cls(language=ArtifactLanguage(value["language"]), description=value["description"])


@dataclass(frozen=True)
class Plan:
    summary: str
    steps: tuple[PlanStep, ...]
    open_questions: tuple[str, ...] = ()

    @property
    def ready_for_approval(self) -> bool:
        return bool(self.steps) and not self.open_questions

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "steps": [step.to_dict() for step in self.steps],
            "open_questions": list(self.open_questions),
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "Plan":
        raw_steps = value.get("steps", [])
        return cls(
            summary=str(value["summary"]),
            steps=tuple(PlanStep.from_dict(step) for step in raw_steps),
            open_questions=tuple(str(question) for question in value.get("open_questions", [])),
        )


@dataclass(frozen=True)
class GeneratedArtifact:
    language: ArtifactLanguage
    filename: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {
            "language": self.language.value,
            "filename": self.filename,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, value: dict[str, str]) -> "GeneratedArtifact":
        return cls(
            language=ArtifactLanguage(value["language"]),
            filename=value["filename"],
            content=value["content"],
        )


@dataclass(frozen=True)
class SecurityFinding:
    rule_id: str
    severity: FindingSeverity
    message: str
    remediation: str
    tool: str = "local-policy"
    location: str | None = None
    evidence: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "remediation": self.remediation,
            "tool": self.tool,
            "location": self.location,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "SecurityFinding":
        return cls(
            rule_id=str(value["rule_id"]),
            severity=FindingSeverity(str(value["severity"])),
            message=str(value["message"]),
            remediation=str(value["remediation"]),
            tool=str(value.get("tool") or "local-policy"),
            location=str(value["location"]) if value.get("location") else None,
            evidence=str(value["evidence"]) if value.get("evidence") else None,
        )


@dataclass(frozen=True)
class ScanReport:
    """Normalized outcome from one required static-analysis tool."""

    tool: str
    succeeded: bool
    findings: tuple[SecurityFinding, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "succeeded": self.succeeded,
            "findings": [finding.to_dict() for finding in self.findings],
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "ScanReport":
        return cls(
            tool=str(value["tool"]),
            succeeded=bool(value["succeeded"]),
            findings=tuple(
                SecurityFinding.from_dict(finding) for finding in value.get("findings", [])
            ),
            error=str(value["error"]) if value.get("error") else None,
        )


@dataclass(frozen=True)
class SandboxResult:
    """Outcome from one isolated Docker validation attempt."""

    succeeded: bool
    summary: str
    output: str = ""
    infracost_breakdown: InfracostBreakdown | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "succeeded": self.succeeded,
            "summary": self.summary,
            "output": self.output,
            "infracost_breakdown": (
                self.infracost_breakdown.to_dict() if self.infracost_breakdown else None
            ),
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "SandboxResult":
        return cls(
            succeeded=bool(value["succeeded"]),
            summary=str(value["summary"]),
            output=str(value.get("output") or ""),
            infracost_breakdown=(
                InfracostBreakdown.from_dict(breakdown)
                if isinstance(breakdown := value.get("infracost_breakdown"), dict)
                else None
            ),
        )


@dataclass(frozen=True)
class RetrievalEvidence:
    """Audit metadata for an internal policy injected into a Coder prompt."""

    rule_id: str
    source: str
    source_hash: str
    score: float

    def to_dict(self) -> dict[str, str | float]:
        return {
            "rule_id": self.rule_id,
            "source": self.source,
            "source_hash": self.source_hash,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "RetrievalEvidence":
        return cls(
            rule_id=str(value["rule_id"]),
            source=str(value["source"]),
            source_hash=str(value["source_hash"]),
            score=float(value["score"]),
        )


@dataclass(frozen=True)
class ContextAudit:
    """Audit evidence when a user request was bounded before model use."""

    original_characters: int
    sent_characters: int
    omitted_characters: int
    omitted_sha256: str | None = None

    def to_dict(self) -> dict[str, int | str | None]:
        return {
            "original_characters": self.original_characters,
            "sent_characters": self.sent_characters,
            "omitted_characters": self.omitted_characters,
            "omitted_sha256": self.omitted_sha256,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "ContextAudit":
        return cls(
            original_characters=int(value["original_characters"]),
            sent_characters=int(value["sent_characters"]),
            omitted_characters=int(value["omitted_characters"]),
            omitted_sha256=str(value["omitted_sha256"])
            if value.get("omitted_sha256")
            else None,
        )


@dataclass(frozen=True)
class ReviewResult:
    verdict: ReviewVerdict
    assessment: str
    findings: tuple[SecurityFinding, ...] = ()
    required_changes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict.value,
            "assessment": self.assessment,
            "findings": [finding.to_dict() for finding in self.findings],
            "required_changes": list(self.required_changes),
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "ReviewResult":
        raw_findings = value.get("findings", [])
        return cls(
            verdict=ReviewVerdict(str(value["verdict"])),
            assessment=str(value["assessment"]),
            findings=tuple(SecurityFinding.from_dict(finding) for finding in raw_findings),
            required_changes=tuple(str(change) for change in value.get("required_changes", [])),
        )


@dataclass(frozen=True)
class FinOpsCostDriver:
    """One Azure cost driver surfaced by the FinOps agent."""

    resource_type: str
    estimated_monthly_usd: float
    sku: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "resource_type": self.resource_type,
            "estimated_monthly_usd": self.estimated_monthly_usd,
            "sku": self.sku,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "FinOpsCostDriver":
        return cls(
            resource_type=str(value["resource_type"]),
            estimated_monthly_usd=float(value["estimated_monthly_usd"]),
            sku=str(value["sku"]),
            notes=str(value["notes"]),
        )


@dataclass(frozen=True)
class InfracostResource:
    """A resource-level monthly price reported by the Infracost CLI."""

    name: str
    resource_type: str
    monthly_cost_usd: float

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "resource_type": self.resource_type,
            "monthly_cost_usd": self.monthly_cost_usd,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "InfracostResource":
        return cls(
            name=str(value["name"]),
            resource_type=str(value.get("resource_type") or "unknown"),
            monthly_cost_usd=float(value.get("monthly_cost_usd") or 0),
        )


@dataclass(frozen=True)
class InfracostBreakdown:
    """Evidence-based Terraform price estimate from an isolated Infracost run."""

    total_monthly_usd: float
    currency: str = "USD"
    resources: tuple[InfracostResource, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "total_monthly_usd": self.total_monthly_usd,
            "currency": self.currency,
            "resources": [resource.to_dict() for resource in self.resources],
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "InfracostBreakdown":
        raw_resources = value.get("resources", [])
        return cls(
            total_monthly_usd=float(value.get("total_monthly_usd") or 0),
            currency=str(value.get("currency") or "USD"),
            resources=tuple(
                InfracostResource.from_dict(resource)
                for resource in raw_resources
                if isinstance(resource, dict)
            ),
            error=str(value["error"]) if value.get("error") else None,
        )


@dataclass(frozen=True)
class FinOpsReport:
    """Cloud cost-projection report produced by the FinOps agent."""

    total_monthly_usd: float
    currency: str
    cost_drivers: tuple[FinOpsCostDriver, ...]
    recommendations: tuple[str, ...]
    raw_assessment: str
    infracost_breakdown: InfracostBreakdown | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "total_monthly_usd": self.total_monthly_usd,
            "currency": self.currency,
            "cost_drivers": [d.to_dict() for d in self.cost_drivers],
            "recommendations": list(self.recommendations),
            "raw_assessment": self.raw_assessment,
            "infracost_breakdown": (
                self.infracost_breakdown.to_dict() if self.infracost_breakdown else None
            ),
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "FinOpsReport":
        return cls(
            total_monthly_usd=float(value["total_monthly_usd"]),
            currency=str(value.get("currency", "USD")),
            cost_drivers=tuple(
                FinOpsCostDriver.from_dict(d) for d in value.get("cost_drivers", [])
            ),
            recommendations=tuple(str(r) for r in value.get("recommendations", [])),
            raw_assessment=str(value.get("raw_assessment", "")),
            infracost_breakdown=(
                InfracostBreakdown.from_dict(breakdown)
                if isinstance(breakdown := value.get("infracost_breakdown"), dict)
                else None
            ),
        )


@dataclass(frozen=True)
class AttackVector(str, Enum):
    """Classification of adversarial attack vectors analyzed by the Red Team."""

    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    NETWORK_PERIMETER_LEAK = "network_perimeter_leak"
    SUPPLY_CHAIN_DEPENDENCY = "supply_chain_dependency"
    SECRET_EXPOSURE = "secret_exposure"
    UNENCRYPTED_STATE = "unencrypted_state"
    OTHER = "other"


@dataclass(frozen=True)
class AttackFinding:
    """One exploitable security vulnerability or attack surface identified by the Red Team."""

    rule_id: str
    severity: FindingSeverity
    vector: AttackVector
    message: str
    remediation: str
    exploit_scenario: str = ""

    def to_security_finding(self) -> SecurityFinding:
        return SecurityFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            message=f"[{self.vector.value}] {self.message}",
            remediation=self.remediation,
            tool="red-team",
            evidence=self.exploit_scenario if self.exploit_scenario else None,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "vector": self.vector.value,
            "message": self.message,
            "remediation": self.remediation,
            "exploit_scenario": self.exploit_scenario,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AttackFinding":
        raw_vector = str(value.get("vector", "other"))
        try:
            vector = AttackVector(raw_vector)
        except ValueError:
            vector = AttackVector.OTHER
        return cls(
            rule_id=str(value["rule_id"]),
            severity=FindingSeverity(str(value["severity"])),
            vector=vector,
            message=str(value["message"]),
            remediation=str(value["remediation"]),
            exploit_scenario=str(value.get("exploit_scenario") or ""),
        )


@dataclass(frozen=True)
class RedTeamReport:
    """Adversarial security assessment produced by the Security Red Team Agent."""

    assessment: str
    risk_score: float  # 0.0 (clean) to 10.0 (critical danger)
    attack_findings: tuple[AttackFinding, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "assessment": self.assessment,
            "risk_score": self.risk_score,
            "attack_findings": [f.to_dict() for f in self.attack_findings],
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "RedTeamReport":
        return cls(
            assessment=str(value.get("assessment", "")),
            risk_score=float(value.get("risk_score", 0.0)),
            attack_findings=tuple(
                AttackFinding.from_dict(f) for f in value.get("attack_findings", [])
            ),
        )


@dataclass(frozen=True)
class WorkflowEvent:
    event_type: str
    agent: str
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, str]:
        return {
            "event_type": self.event_type,
            "agent": self.agent,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, str]) -> "WorkflowEvent":
        return cls(
            event_type=value["event_type"],
            agent=value["agent"],
            message=value["message"],
            created_at=datetime.fromisoformat(value["created_at"]),
        )


@dataclass
class WorkflowRun:
    user_request: str
    run_id: str = field(default_factory=lambda: str(uuid4()))
    submitted_by_user_id: str | None = None
    status: RunStatus = RunStatus.SUBMITTED
    event_schema_version: int = WORKFLOW_EVENT_SCHEMA_VERSION
    plan: Plan | None = None
    retrieved_rules: tuple[str, ...] = ()
    retrieval_evidence: tuple[RetrievalEvidence, ...] = ()
    context_audits: list[ContextAudit] = field(default_factory=list)
    artifacts: list[GeneratedArtifact] = field(default_factory=list)
    scans: list[ScanReport] = field(default_factory=list)
    reviews: list[ReviewResult] = field(default_factory=list)
    sandbox_results: list[SandboxResult] = field(default_factory=list)
    finops_reports: list[FinOpsReport] = field(default_factory=list)
    red_team_reports: list[RedTeamReport] = field(default_factory=list)
    auto_fix_attempts: int = 0
    token_usage: list[TokenUsageRecord] = field(default_factory=list)
    events: list[WorkflowEvent] = field(default_factory=list)

    def transition(self, target: RunStatus, agent: str, message: str) -> None:
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"Cannot transition from {self.status.value} to {target.value}")
        self.status = target
        self.events.append(WorkflowEvent(event_type=target.value, agent=agent, message=message))

    def add_event(
        self,
        event_type: str | WorkflowEventType,
        agent: str,
        message: str,
    ) -> None:
        value = event_type.value if isinstance(event_type, WorkflowEventType) else event_type
        self.events.append(WorkflowEvent(event_type=value, agent=agent, message=message))

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "user_request": self.user_request,
            "submitted_by_user_id": self.submitted_by_user_id,
            "status": self.status.value,
            "event_schema_version": self.event_schema_version,
            "plan": self.plan.to_dict() if self.plan else None,
            "retrieved_rules": list(self.retrieved_rules),
            "retrieval_evidence": [evidence.to_dict() for evidence in self.retrieval_evidence],
            "context_audits": [audit.to_dict() for audit in self.context_audits],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "scans": [scan.to_dict() for scan in self.scans],
            "reviews": [review.to_dict() for review in self.reviews],
            "sandbox_results": [result.to_dict() for result in self.sandbox_results],
            "finops_reports": [report.to_dict() for report in self.finops_reports],
            "red_team_reports": [report.to_dict() for report in self.red_team_reports],
            "auto_fix_attempts": self.auto_fix_attempts,
            "token_usage": [record.to_dict() for record in self.token_usage],
            "events": [event.to_dict() for event in self.events],
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "WorkflowRun":
        raw_plan = value.get("plan")
        return cls(
            run_id=str(value["run_id"]),
            user_request=str(value["user_request"]),
            submitted_by_user_id=(
                str(value["submitted_by_user_id"])
                if value.get("submitted_by_user_id")
                else None
            ),
            status=RunStatus(str(value["status"])),
            event_schema_version=int(
                value.get("event_schema_version", WORKFLOW_EVENT_SCHEMA_VERSION)
            ),
            plan=Plan.from_dict(raw_plan) if isinstance(raw_plan, dict) else None,
            retrieved_rules=tuple(str(rule) for rule in value.get("retrieved_rules", [])),
            retrieval_evidence=tuple(
                RetrievalEvidence.from_dict(evidence)
                for evidence in value.get("retrieval_evidence", [])
            ),
            context_audits=[
                ContextAudit.from_dict(audit) for audit in value.get("context_audits", [])
            ],
            artifacts=[
                GeneratedArtifact.from_dict(artifact) for artifact in value.get("artifacts", [])
            ],
            scans=[ScanReport.from_dict(scan) for scan in value.get("scans", [])],
            reviews=[ReviewResult.from_dict(review) for review in value.get("reviews", [])],
            sandbox_results=[
                SandboxResult.from_dict(result) for result in value.get("sandbox_results", [])
            ],
            finops_reports=[
                FinOpsReport.from_dict(r) for r in value.get("finops_reports", [])
            ],
            red_team_reports=[
                RedTeamReport.from_dict(r) for r in value.get("red_team_reports", [])
            ],
            auto_fix_attempts=int(value.get("auto_fix_attempts", 0)),
            token_usage=[
                TokenUsageRecord.from_dict(record) for record in value.get("token_usage", [])
            ],
            events=[WorkflowEvent.from_dict(event) for event in value.get("events", [])],
        )


_ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.SUBMITTED: {RunStatus.BLOCKED, RunStatus.PLANNING, RunStatus.FAILED},
    RunStatus.BLOCKED: set(),
    RunStatus.PLANNING: {
        RunStatus.AWAITING_APPROVAL,
        RunStatus.NEEDS_CLARIFICATION,
        RunStatus.FAILED,
    },
    RunStatus.NEEDS_CLARIFICATION: {RunStatus.PLANNING, RunStatus.FAILED},
    RunStatus.AWAITING_APPROVAL: {RunStatus.PLANNING, RunStatus.CODING, RunStatus.FAILED},
    RunStatus.CODING: {RunStatus.SCANNING, RunStatus.FAILED},
    RunStatus.AUTO_FIXING: {RunStatus.SCANNING, RunStatus.FAILED},
    RunStatus.SCANNING: {
        RunStatus.AUTO_FIXING,
        RunStatus.REVIEWING,
        RunStatus.NEEDS_MANUAL_INTERVENTION,
        RunStatus.FAILED,
    },
    RunStatus.REVIEWING: {
        RunStatus.CODING,
        RunStatus.APPROVED,
        RunStatus.NEEDS_MANUAL_INTERVENTION,
        RunStatus.FAILED,
    },
    RunStatus.APPROVED: {RunStatus.SANDBOXING, RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.SANDBOXING: {
        RunStatus.COMPLETED,
        RunStatus.NEEDS_MANUAL_INTERVENTION,
        RunStatus.FAILED,
    },
    RunStatus.COMPLETED: set(),
    RunStatus.NEEDS_MANUAL_INTERVENTION: set(),
    RunStatus.FAILED: set(),
}
