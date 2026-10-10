choco install minikube -y --no-progress"""FastAPI service wrapping the MagentAutoGen WorkflowOrchestrator."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.auth import (
    AuthenticatedUser,
    get_current_user,
    require_role,
    require_separate_approver,
    verify_auth,
)
from src.app_factory import create_azure_orchestrator, create_orchestrator
from src.integrations.github_exporter import GitHubExporter, GitHubExportError
from src.utils.audit_log import get_audit_logger
from src.utils.cost_tracker import CostTracker
from src.utils.redaction import redact_mapping
from src.utils.structured_logging import configure_logging
from src.utils.telemetry import configure_telemetry, instrument_fastapi
from src.workflow.models import ArtifactLanguage, Plan, PlanStep, RunStatus
from src.workflow.orchestrator import WorkflowStateError
from src.workflow.store import RunNotFoundError

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class SubmitRequest(BaseModel):
    user_request: str


class RejectRequest(BaseModel):
    feedback: str


class PlanStepUpdate(BaseModel):
    language: ArtifactLanguage
    description: str


class PlanUpdateRequest(BaseModel):
    summary: str
    steps: list[PlanStepUpdate]


# ---------------------------------------------------------------------------
# Global orchestrator (initialised once per process)
# ---------------------------------------------------------------------------

_orchestrator: Any = None
workflow_runs_total = Counter(
    "workflow_runs_total",
    "Completed workflow outcomes.",
    ("outcome",),
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    global _orchestrator
    configure_logging()
    configure_telemetry()
    provider_mode = os.getenv("MAGENT_PROVIDER", "demo").lower()
    _orchestrator = (
        create_azure_orchestrator()
        if provider_mode == "azure"
        else create_orchestrator()
    )
    yield


app = FastAPI(
    title="MagentAutoGen API",
    description="REST and SSE backend for the MagentAutoGen approval-gated workflow.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
instrument_fastapi(app)
Instrumentator().instrument(app).expose(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_response(run) -> dict[str, Any]:
    """Return a redacted dict representation of a WorkflowRun."""
    return redact_mapping(run.to_dict())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/me")
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Return the authenticated caller identity (Entra ID, API Key, or Local Dev)."""
    return current_user.to_dict()


@app.post("/api/runs", dependencies=[Depends(verify_auth)])
async def submit_run(
    body: SubmitRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Submit a new user request and begin planning."""
    try:
        run = await _orchestrator.submit(body.user_request)
        run.submitted_by_user_id = current_user.user_id
        _orchestrator.run_store.save(run)
        get_audit_logger().mission_submitted(
            user_id=current_user.user_id,
            username=current_user.username,
            auth_type=current_user.auth_type,
            run_id=run.run_id,
            request_preview=body.user_request,
        )
        return _run_response(run)
    except WorkflowStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs", dependencies=[Depends(verify_auth)])
async def list_runs(limit: int = 50):
    """List recent workflow runs for the control plane dashboard."""
    if _orchestrator is None or not hasattr(_orchestrator, "run_store"):
        return []
    runs = _orchestrator.run_store.list_recent(limit=limit)
    return [_run_response(r) for r in runs]


@app.get("/api/runs/{run_id}", dependencies=[Depends(verify_auth)])
async def get_run(run_id: str):
    """Return the current state of a workflow run."""
    try:
        run = _orchestrator.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    return _run_response(run)


@app.delete("/api/runs/{run_id}", dependencies=[Depends(verify_auth)])
async def delete_run(
    run_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Delete a workflow run and its persisted state."""
    try:
        _orchestrator.delete_run(run_id)
        get_audit_logger().mission_deleted(
            user_id=current_user.user_id,
            username=current_user.username,
            auth_type=current_user.auth_type,
            run_id=run_id,
        )
        return {"status": "deleted", "run_id": run_id}
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.post("/api/runs/{run_id}/approve")
async def approve_run(
    run_id: str,
    current_user: AuthenticatedUser = Depends(require_role("approver")),
):
    """Approve a plan and trigger the coding / review loop."""
    try:
        pending_run = _orchestrator.get_run(run_id)
        require_separate_approver(current_user, pending_run.submitted_by_user_id)
        run = await _orchestrator.approve(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except WorkflowStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_audit_logger().plan_approved(
        user_id=current_user.user_id,
        username=current_user.username,
        auth_type=current_user.auth_type,
        run_id=run_id,
    )
    if run.status in {RunStatus.APPROVED, RunStatus.COMPLETED}:
        workflow_runs_total.labels(outcome="approved").inc()
    elif run.status in {RunStatus.FAILED, RunStatus.NEEDS_MANUAL_INTERVENTION}:
        workflow_runs_total.labels(outcome="failed").inc()
    return _run_response(run)


@app.post("/api/runs/{run_id}/reject")
async def reject_run(
    run_id: str,
    body: RejectRequest,
    current_user: AuthenticatedUser = Depends(require_role("approver")),
):
    """Reject a plan with feedback and return a revised plan."""
    try:
        pending_run = _orchestrator.get_run(run_id)
        require_separate_approver(current_user, pending_run.submitted_by_user_id)
        run = await _orchestrator.reject(run_id, body.feedback)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except WorkflowStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_audit_logger().plan_rejected(
        user_id=current_user.user_id,
        username=current_user.username,
        auth_type=current_user.auth_type,
        run_id=run_id,
        feedback_preview=body.feedback,
    )
    workflow_runs_total.labels(outcome="rejected").inc()
    return _run_response(run)


@app.patch("/api/runs/{run_id}/plan", dependencies=[Depends(verify_auth)])
async def update_plan(
    run_id: str,
    body: PlanUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Save operator edits to a plan that is still awaiting approval."""
    summary = body.summary.strip()
    steps = tuple(
        PlanStep(language=step.language, description=step.description.strip())
        for step in body.steps
    )
    if not summary or not steps or any(not step.description for step in steps):
        raise HTTPException(
            status_code=400,
            detail="Plan summary and every step description must be non-empty.",
        )
    try:
        run = _orchestrator.update_plan(run_id, Plan(summary=summary, steps=steps))
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except WorkflowStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    get_audit_logger().log(
        "plan_updated",
        user_id=current_user.user_id,
        username=current_user.username,
        auth_type=current_user.auth_type,
        run_id=run_id,
        summary_preview=summary,
        step_count=len(steps),
    )
    return redact_mapping(run.plan.to_dict())


@app.post("/api/runs/{run_id}/export/github", dependencies=[Depends(verify_auth)])
async def export_run_to_github(
    run_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a pull request containing artifacts from a completed workflow run."""
    try:
        run = _orchestrator.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    if run.status is not RunStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="Only completed runs can be exported to GitHub.",
        )

    try:
        result = GitHubExporter.from_environment().export(run)
    except GitHubExportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    get_audit_logger().log(
        "github_pr_exported",
        user_id=current_user.user_id,
        username=current_user.username,
        auth_type=current_user.auth_type,
        run_id=run_id,
        branch=result.branch,
        pull_request_number=result.pull_request_number,
    )
    return redact_mapping(result.to_dict())


@app.get("/api/runs/{run_id}/finops", dependencies=[Depends(verify_auth)])
async def get_finops(run_id: str):
    """Return token usage and cost estimates for a run."""
    try:
        run = _orchestrator.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    tracker = getattr(_orchestrator, "cost_tracker", None) or CostTracker()
    summary = tracker.session_summary(run_id, records=run.token_usage)

    return redact_mapping(
        {
            "run_id": run_id,
            "status": run.status.value,
            "total_usd": summary.total_usd,
            "total_prompt_tokens": summary.total_prompt_tokens,
            "total_completion_tokens": summary.total_completion_tokens,
            "per_agent": summary.per_agent,
            "per_stage": summary.per_stage,
            "per_operation": summary.per_operation,
            "disclaimer": summary.disclaimer,
        }
    )


@app.get("/api/runs/{run_id}/events/stream", dependencies=[Depends(verify_auth)])
async def stream_events(run_id: str):
    """Server-Sent Events stream of workflow events."""
    try:
        _orchestrator.get_run(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    async def event_generator():
        last_count = 0
        poll_interval = 0.5  # seconds

        while True:
            try:
                run = _orchestrator.get_run(run_id)
            except RunNotFoundError:
                yield f"event: error\ndata: {json.dumps({'message': 'Run not found'})}\n\n"
                break

            events = sorted(run.events, key=lambda e: e.created_at)
            if len(events) > last_count:
                for event in events[last_count:]:
                    payload = json.dumps(redact_mapping(event.to_dict()))
                    yield f"data: {payload}\n\n"
                last_count = len(events)

            # Terminal states — close the stream so the client can reconnect
            # or simply stop if the run is finished.
            if run.status in {
                RunStatus.COMPLETED,
                RunStatus.BLOCKED,
                RunStatus.NEEDS_MANUAL_INTERVENTION,
                RunStatus.FAILED,
            }:
                yield f"event: terminal\ndata: {json.dumps({'status': run.status.value})}\n\n"
                break

            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
