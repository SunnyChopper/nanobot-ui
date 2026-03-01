"""Workflow registry and run history HTTP handlers."""

from __future__ import annotations

from fastapi import HTTPException, Request

from nanobot.config.loader import get_data_dir
from server.agents.registry import (
    delete_workflow,
    get_workflow,
    get_workflow_run,
    list_workflow_runs,
    list_workflows,
    run_workflow,
    save_workflow,
)


async def list_workflows_handler(request: Request) -> list[dict]:
    """List all registered workflows with id, name, description, status, last_run_at, last_run_outcome."""
    data_dir = get_data_dir()
    workflows = list_workflows(data_dir)
    for wf in workflows:
        runs = list_workflow_runs(data_dir, workflow_id=wf["id"], limit=1, offset=0)
        if runs:
            r = runs[0]
            wf["last_run_at"] = r.get("started_at_ms")
            wf["last_run_outcome"] = r.get("status")
        else:
            wf["last_run_at"] = None
            wf["last_run_outcome"] = None
    return workflows


async def get_workflow_handler(workflow_id: str, request: Request) -> dict:
    """Get full workflow definition by id."""
    data_dir = get_data_dir()
    definition = get_workflow(data_dir, workflow_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return definition


async def create_workflow_handler(body: dict, request: Request) -> dict:
    """Create a new workflow. Body must include id (or name used as id), name, nodes, edges."""
    data_dir = get_data_dir()
    wf_id = body.get("id") or body.get("name") or "workflow"
    if not wf_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Workflow id must be alphanumeric (with - or _)")
    definition = {
        "id": wf_id,
        "name": body.get("name") or wf_id,
        "description": body.get("description") or "",
        "status": body.get("status") or "draft",
        "nodes": body.get("nodes") or [],
        "edges": body.get("edges") or [],
    }
    save_workflow(data_dir, wf_id, definition)
    return definition


async def update_workflow_handler(workflow_id: str, body: dict, request: Request) -> dict:
    """Update an existing workflow definition (partial merge)."""
    data_dir = get_data_dir()
    existing = get_workflow(data_dir, workflow_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    definition = {**existing, **{k: v for k, v in body.items() if v is not None}}
    save_workflow(data_dir, workflow_id, definition)
    return definition


async def delete_workflow_handler(workflow_id: str, request: Request) -> None:
    """Permanently delete a workflow definition. Returns 204 No Content."""
    data_dir = get_data_dir()
    if not get_workflow(data_dir, workflow_id):
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    deleted = delete_workflow(data_dir, workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    # Return None; route uses status_code=204 so no body is sent


async def run_workflow_handler(workflow_id: str, request: Request, body: dict | None = None) -> dict:
    """Run a workflow with optional input payload. Body may include force=True to bypass same-day idempotency. Returns run_id."""
    data_dir = get_data_dir()
    agent = getattr(request.app.state, "agent", None)
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not available")
    body = body or {}
    input_payload = body.get("input") if isinstance(body, dict) else None
    force = body.get("force") is True
    try:
        run_id = await run_workflow(data_dir, workflow_id, agent, input_payload, force=force)
        return {"run_id": run_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


async def list_workflow_runs_handler(
    request: Request,
    workflow_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List workflow runs, optionally filtered by workflow_id."""
    data_dir = get_data_dir()
    return list_workflow_runs(data_dir, workflow_id=workflow_id, limit=limit, offset=offset)


async def get_workflow_run_handler(run_id: str, request: Request) -> dict:
    """Get a single run by run_id."""
    data_dir = get_data_dir()
    run = get_workflow_run(data_dir, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run
