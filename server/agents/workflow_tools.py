"""
Nanobot tools for listing, describing, running, and managing workflows.

Register these in server bootstrap so the agent can reason about workflows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

from server.agents.registry import (
    get_workflow,
    get_workflow_run,
    list_workflow_runs,
    list_workflows,
    run_workflow,
    save_workflow,
)

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop


def _summary_line(w: dict[str, Any]) -> str:
    name = w.get("name") or w.get("id") or ""
    desc = (w.get("description") or "")[:60]
    status = w.get("status") or "draft"
    last = w.get("last_run_outcome") or "—"
    return f"- {name} (id={w.get('id')}, status={status}, last_run={last}) {desc}"


class WorkflowListTool(Tool):
    """List registered workflows with summary."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    @property
    def name(self) -> str:
        return "workflow_list"

    @property
    def description(self) -> str:
        return "List all registered agent workflows with id, name, status, and last run outcome."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        workflows = list_workflows(self._data_dir)
        if not workflows:
            return "No workflows registered."
        return "Workflows:\n" + "\n".join(_summary_line(w) for w in workflows)


class WorkflowGetTool(Tool):
    """Get full definition and recent runs for a workflow."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    @property
    def name(self) -> str:
        return "workflow_get"

    @property
    def description(self) -> str:
        return "Get workflow definition and recent runs by workflow id."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "Workflow id"},
            },
            "required": ["workflow_id"],
        }

    async def execute(self, workflow_id: str, **kwargs: Any) -> str:
        definition = get_workflow(self._data_dir, workflow_id)
        if not definition:
            return f"Workflow '{workflow_id}' not found."
        runs = list_workflow_runs(self._data_dir, workflow_id=workflow_id, limit=5)
        out = [
            f"Name: {definition.get('name') or workflow_id}",
            f"Description: {definition.get('description') or '(none)'}",
            f"Status: {definition.get('status') or 'draft'}",
            f"Nodes: {[n.get('name') or n.get('id') for n in definition.get('nodes') or []]}",
            f"Edges: {definition.get('edges') or []}",
        ]
        if runs:
            out.append("Recent runs:")
            for r in runs:
                out.append(f"  {r.get('run_id')} status={r.get('status')} at {r.get('started_at_ms')}")
        return "\n".join(out)


class WorkflowRunTool(Tool):
    """Run a workflow by id with optional input."""

    def __init__(self, data_dir: Path, agent: "AgentLoop"):
        self._data_dir = data_dir
        self._agent = agent

    @property
    def name(self) -> str:
        return "workflow_run"

    @property
    def description(self) -> str:
        return "Run a workflow by id. Optional input payload (JSON object)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "Workflow id to run"},
                "input_json": {"type": "string", "description": "Optional JSON object as string for input"},
            },
            "required": ["workflow_id"],
        }

    async def execute(
        self,
        workflow_id: str,
        input_json: str = "",
        **kwargs: Any,
    ) -> str:
        input_payload = None
        if input_json and input_json.strip():
            try:
                input_payload = json.loads(input_json)
            except json.JSONDecodeError:
                return "Invalid input_json: must be valid JSON."
        try:
            run_id = await run_workflow(
                self._data_dir,
                workflow_id,
                self._agent,
                input_payload,
            )
            return f"Workflow run started: {run_id}"
        except ValueError as e:
            return f"Error: {e}"


class WorkflowCreateTool(Tool):
    """Create a new workflow from name, description, nodes, edges."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    @property
    def name(self) -> str:
        return "workflow_create"

    @property
    def description(self) -> str:
        return "Create a new workflow. Provide id (or name), name, optional description, nodes (list of {id, name, type, prompt}), edges (list of {from, to})."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "Unique id (alphanumeric, - or _)"},
                "name": {"type": "string", "description": "Display name"},
                "description": {"type": "string", "description": "Optional description"},
                "nodes_json": {"type": "string", "description": "JSON array of nodes: [{id, name?, type?, prompt?}]"},
                "edges_json": {"type": "string", "description": "JSON array of edges: [{from, to}]"},
            },
            "required": ["workflow_id", "name"],
        }

    async def execute(
        self,
        workflow_id: str,
        name: str,
        description: str = "",
        nodes_json: str = "[]",
        edges_json: str = "[]",
        **kwargs: Any,
    ) -> str:
        try:
            nodes = json.loads(nodes_json) if nodes_json.strip() else []
            edges = json.loads(edges_json) if edges_json.strip() else []
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"
        definition = {
            "id": workflow_id,
            "name": name,
            "description": description,
            "status": "draft",
            "nodes": nodes,
            "edges": edges,
        }
        save_workflow(self._data_dir, workflow_id, definition)
        return f"Workflow '{workflow_id}' created. Use workflow_update to change it."


class WorkflowUpdateTool(Tool):
    """Update an existing workflow (partial)."""

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    @property
    def name(self) -> str:
        return "workflow_update"

    @property
    def description(self) -> str:
        return "Update a workflow. Provide workflow_id and any of: name, description, status, nodes_json, edges_json."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "Workflow id to update"},
                "name": {"type": "string", "description": "New display name"},
                "description": {"type": "string", "description": "New description"},
                "status": {"type": "string", "enum": ["draft", "active"], "description": "draft or active"},
                "nodes_json": {"type": "string", "description": "JSON array of nodes"},
                "edges_json": {"type": "string", "description": "JSON array of edges"},
            },
            "required": ["workflow_id"],
        }

    async def execute(
        self,
        workflow_id: str,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        nodes_json: str | None = None,
        edges_json: str | None = None,
        **kwargs: Any,
    ) -> str:
        existing = get_workflow(self._data_dir, workflow_id)
        if not existing:
            return f"Workflow '{workflow_id}' not found."
        updates = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if status is not None:
            updates["status"] = status
        if nodes_json is not None and nodes_json.strip():
            try:
                updates["nodes"] = json.loads(nodes_json)
            except json.JSONDecodeError as e:
                return f"Invalid nodes_json: {e}"
        if edges_json is not None and edges_json.strip():
            try:
                updates["edges"] = json.loads(edges_json)
            except json.JSONDecodeError as e:
                return f"Invalid edges_json: {e}"
        definition = {**existing, **updates}
        save_workflow(self._data_dir, workflow_id, definition)
        return f"Workflow '{workflow_id}' updated."


def create_workflow_tools(data_dir: Path, agent: "AgentLoop") -> list[Tool]:
    """Create workflow tools for registration with the agent."""
    return [
        WorkflowListTool(data_dir),
        WorkflowGetTool(data_dir),
        WorkflowRunTool(data_dir, agent),
        WorkflowCreateTool(data_dir),
        WorkflowUpdateTool(data_dir),
    ]
