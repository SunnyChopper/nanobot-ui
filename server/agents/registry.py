"""
Workflow registry: list, get, save definitions and run workflows.

Uses server.db for persistence. Running a workflow builds the graph,
invokes it, and persists the result envelope.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from server.agents.graph import NodeExecutionError, run_graph
from server.db import (
    create_run,
    get_last_successful_run_for_workflow_on_date,
    get_run,
    list_runs_for_workflow,
    list_workflow_ids,
    load_workflow_definition,
    save_workflow_definition,
    update_run_finished,
    update_run_started,
)

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop


def list_workflows(data_dir: Path) -> list[dict[str, Any]]:
    """List all workflows with id, name, description, status (from definition files)."""
    result = []
    for wf_id in list_workflow_ids(data_dir):
        definition = load_workflow_definition(data_dir, wf_id)
        if definition:
            result.append({
                "id": wf_id,
                "name": definition.get("name") or wf_id,
                "description": definition.get("description") or "",
                "status": definition.get("status") or "draft",
            })
    return result


def build_workflow_summary(data_dir: Path, max_chars: int = 2000) -> str:
    """Build a concise serialized summary of registered workflows for context injection.
    Includes nodes, edges, and last run outcome so the agent can describe workflows
    without loading full definitions. Optimized for token cost."""
    workflows = list_workflows(data_dir)
    if not workflows:
        return "No workflows registered."
    lines = []
    for w in workflows:
        wf_id = w.get("id") or ""
        name = w.get("name") or wf_id
        status = w.get("status") or "draft"
        desc = (w.get("description") or "")[:60]
        runs = list_runs_for_workflow(data_dir, name, limit=1, offset=0)
        last_outcome = runs[0].get("status") if runs else None
        definition = load_workflow_definition(data_dir, wf_id)
        node_ids = [n.get("id") or "" for n in (definition.get("nodes") or []) if n.get("id")]
        edges_cfg = definition.get("edges") or []
        edge_str = ",".join(f"{e.get('from')}→{e.get('to')}" for e in edges_cfg[:10])
        if len(edges_cfg) > 10:
            edge_str += "..."
        line = f"- {wf_id}: {name} ({status})"
        if last_outcome:
            line += f" last_run={last_outcome}"
        if desc:
            line += f" — {desc}"
        line += f" | nodes=[{','.join(node_ids)}] edges=[{edge_str}]"
        lines.append(line)
    out = "Registered workflows (use workflow_get <id> for full def, workflow_run to run):\n" + "\n".join(lines)
    return out[:max_chars] + ("..." if len(out) > max_chars else "")


def get_workflow(data_dir: Path, workflow_id: str) -> dict[str, Any] | None:
    """Get full workflow definition by id."""
    return load_workflow_definition(data_dir, workflow_id)


def save_workflow(data_dir: Path, workflow_id: str, definition: dict[str, Any]) -> None:
    """Persist workflow definition."""
    save_workflow_definition(data_dir, workflow_id, definition)
    logger.info(f"Workflow saved: {workflow_id}")


def delete_workflow(data_dir: Path, workflow_id: str) -> bool:
    """Remove workflow definition. Returns True if deleted."""
    from server.db import delete_workflow_definition
    return delete_workflow_definition(data_dir, workflow_id)


async def run_workflow(
    data_dir: Path,
    workflow_id: str,
    agent: "AgentLoop",
    input_payload: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    force: bool = False,
) -> str:
    """
    Run a workflow: create run record, execute graph, persist result.

    When force is True (e.g. manual "Run now"), idempotency is
    skipped so the workflow runs even if it already succeeded.

    Returns run_id. LangSmith tracing is used automatically if
    LANGCHAIN_TRACING_V2 and LANGCHAIN_API_KEY are set.
    """
    definition = load_workflow_definition(data_dir, workflow_id)
    if not definition:
        raise ValueError(f"Workflow not found: {workflow_id}")

    workflow_name = definition.get("name") or workflow_id
    idempotent = definition.get("idempotent") == "day"
    if idempotent and not force:
        from datetime import datetime
        date_iso = datetime.now().strftime("%Y-%m-%d")
        existing = get_last_successful_run_for_workflow_on_date(
            data_dir, workflow_name, date_iso
        )
        if existing:
            run_id = create_run(
                data_dir,
                workflow_name=workflow_name,
                input_snapshot=input_payload,
                run_id=run_id,
            )
            update_run_finished(
                data_dir,
                run_id,
                status="skipped",
                error_message="Duplicate run skipped (same-day idempotency)",
            )
            logger.info(f"Workflow {workflow_id} skipped (already ran today)")
            return run_id

    run_id = create_run(
        data_dir,
        workflow_name=definition.get("name") or workflow_id,
        input_snapshot=input_payload,
        run_id=run_id,
    )
    try:
        update_run_started(data_dir, run_id)
        result_state = await run_graph(
            definition,
            agent,
            run_id,
            data_dir,
            input_payload,
        )
        result_envelope = {
            "steps": result_state.get("steps") or [],
            "last_output": result_state.get("last_output") or "",
            "input": result_state.get("input") or {},
        }
        update_run_finished(
            data_dir,
            run_id,
            status="success",
            result_envelope=result_envelope,
        )
        return run_id
    except NodeExecutionError as e:
        logger.exception(f"Workflow {workflow_id} run {run_id} failed at node {e.node_id}")
        update_run_finished(
            data_dir,
            run_id,
            status="error",
            error_message=str(e),
            error_node=e.node_id,
            error_detail={
                "stack_trace": e.stack_trace,
                "node_input_snapshot": e.node_input_snapshot,
            },
        )
        raise
    except Exception as e:
        logger.exception(f"Workflow {workflow_id} run {run_id} failed")
        update_run_finished(
            data_dir,
            run_id,
            status="error",
            error_message=str(e),
        )
        raise


def get_workflow_run(data_dir: Path, run_id: str) -> dict[str, Any] | None:
    """Get a single run by id."""
    return get_run(data_dir, run_id)


def list_workflow_runs(
    data_dir: Path,
    workflow_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List runs, optionally filtered by workflow name."""
    if workflow_id:
        definition = load_workflow_definition(data_dir, workflow_id)
        workflow_name = definition.get("name") or workflow_id if definition else workflow_id
        return list_runs_for_workflow(data_dir, workflow_name, limit=limit, offset=offset)
    from server.db import list_runs
    return list_runs(data_dir, limit=limit, offset=offset)


def get_mcp_usage_by_workflows(data_dir: Path) -> dict[str, list[str]]:
    """
    Return which workflows use which MCP server names.

    Keys are MCP server names (from config); values are lists of workflow ids
    that reference that server in any node's mcp_tools or similar.
    """
    usage: dict[str, list[str]] = {}
    for wf_id in list_workflow_ids(data_dir):
        definition = load_workflow_definition(data_dir, wf_id)
        if not definition:
            continue
        for node in definition.get("nodes") or []:
            tools = node.get("mcp_tools") or node.get("tools") or []
            if isinstance(tools, list):
                for t in tools:
                    name = t if isinstance(t, str) else (t.get("server") or t.get("name") or "")
                    if name:
                        usage.setdefault(name, []).append(wf_id)
            elif isinstance(tools, dict):
                for name in tools:
                    usage.setdefault(name, []).append(wf_id)
    # Deduplicate workflow ids per server
    for k in usage:
        usage[k] = list(dict.fromkeys(usage[k]))
    return usage
