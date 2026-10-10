"""Unit tests for all RunStore implementations."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.workflow.models import (
    ArtifactLanguage,
    AttackFinding,
    AttackVector,
    FindingSeverity,
    FinOpsCostDriver,
    FinOpsReport,
    GeneratedArtifact,
    InfracostBreakdown,
    InfracostResource,
    RedTeamReport,
    RunStatus,
    WorkflowRun,
)
from src.workflow.store import (
    FileRunStore,
    InMemoryRunStore,
    PostgresRunStore,
    RunNotFoundError,
    SqlRunStore,
)


def _sample_workflow_run(run_id: str = "run-sample-001") -> WorkflowRun:
    run = WorkflowRun(
        user_request="Create secure Azure Key Vault",
        run_id=run_id,
        submitted_by_user_id="operator-1",
    )
    run.status = RunStatus.APPROVED
    run.artifacts.append(
        GeneratedArtifact(
            language=ArtifactLanguage.TERRAFORM,
            filename="main.tf",
            content='resource "azurerm_key_vault" "kv" { name = "kv-sample" }',
        )
    )
    run.finops_reports.append(
        FinOpsReport(
            total_monthly_usd=12.50,
            currency="USD",
            cost_drivers=(
                FinOpsCostDriver(
                    resource_type="Key Vault",
                    estimated_monthly_usd=12.50,
                    sku="Standard",
                    notes="Standard tier pricing",
                ),
            ),
            recommendations=("Enable soft delete",),
            raw_assessment="Cost estimate complete",
            infracost_breakdown=InfracostBreakdown(
                total_monthly_usd=11.20,
                resources=(
                    InfracostResource(
                        name="azurerm_key_vault.kv",
                        resource_type="azurerm_key_vault",
                        monthly_cost_usd=11.20,
                    ),
                ),
            ),
        )
    )
    run.red_team_reports.append(
        RedTeamReport(
            assessment="Adversarial evaluation complete",
            risk_score=4.2,
            attack_findings=(
                AttackFinding(
                    rule_id="RT-010",
                    severity=FindingSeverity.LOW,
                    vector=AttackVector.UNENCRYPTED_STATE,
                    message="Verify state locking",
                    remediation="Use Azure Blob backend with lease",
                ),
            ),
        )
    )
    return run


def test_file_run_store_crud() -> None:
    with TemporaryDirectory() as tmp_dir:
        store = FileRunStore(Path(tmp_dir))
        run = _sample_workflow_run()

        # Save
        store.save(run)

        # Load
        loaded = store.load(run.run_id)
        assert loaded.run_id == run.run_id
        assert loaded.user_request == run.user_request
        assert loaded.status == RunStatus.APPROVED
        assert loaded.submitted_by_user_id == "operator-1"
        assert len(loaded.finops_reports) == 1
        assert loaded.finops_reports[0].infracost_breakdown is not None
        assert loaded.finops_reports[0].infracost_breakdown.total_monthly_usd == 11.20
        assert len(loaded.red_team_reports) == 1

        # List recent
        recent = store.list_recent(10)
        assert len(recent) == 1
        assert recent[0].run_id == run.run_id

        # Not found
        with pytest.raises(RunNotFoundError):
            store.load("non-existent-run")


def test_in_memory_run_store_crud() -> None:
    store = InMemoryRunStore()
    run = _sample_workflow_run("mem-run-001")

    store.save(run)
    loaded = store.load(run.run_id)
    assert loaded.run_id == "mem-run-001"
    assert len(store.list_recent(5)) == 1

    with pytest.raises(RunNotFoundError):
        store.load("missing-run")


def test_sql_run_store_in_memory() -> None:
    store = SqlRunStore(":memory:")
    run = _sample_workflow_run("sql-mem-001")

    # Save
    store.save(run)

    # Load
    loaded = store.load("sql-mem-001")
    assert loaded.run_id == "sql-mem-001"
    assert loaded.status == RunStatus.APPROVED
    assert loaded.red_team_reports[0].risk_score == 4.2

    # Update (UPSERT)
    run.status = RunStatus.COMPLETED
    store.save(run)
    updated = store.load("sql-mem-001")
    assert updated.status == RunStatus.COMPLETED

    # List recent
    recent = store.list_recent(10)
    assert len(recent) == 1

    # Not found
    with pytest.raises(RunNotFoundError):
        store.load("sql-non-existent")


def test_sql_run_store_file() -> None:
    with TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "runs.db"
        store = SqlRunStore(db_path)

        for idx in range(5):
            store.save(_sample_workflow_run(f"run-{idx:03d}"))

        recent = store.list_recent(3)
        assert len(recent) == 3
        store.close()


def test_postgres_run_store_sqlite_delegation() -> None:
    with TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "postgres_compat.db"
        store = PostgresRunStore(f"sqlite:///{db_file}")

        run = _sample_workflow_run("pg-compat-001")
        store.save(run)

        loaded = store.load("pg-compat-001")
        assert loaded.run_id == "pg-compat-001"
        assert loaded.user_request == run.user_request
        assert len(loaded.finops_reports) == 1
        assert len(loaded.red_team_reports) == 1

        with pytest.raises(RunNotFoundError):
            store.load("pg-non-existent")

        if store._sqlite_fallback:
            store._sqlite_fallback.close()
