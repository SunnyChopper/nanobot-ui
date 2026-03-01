"""
Build and run a LangGraph StateGraph from a workflow definition.

Nanobot nodes invoke the nanobot engine via run_nanobot_node.
LangSmith tracing is enabled via env (LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY).
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from loguru import logger

from server.agents.context import RuntimeContext
from server.agents.invoker import run_nanobot_node


class NodeExecutionError(Exception):
    """Raised when a workflow node fails; carries node id and detail for run record."""

    def __init__(
        self,
        node_id: str,
        message: str,
        node_input_snapshot: dict[str, Any] | None = None,
        stack_trace: str | None = None,
    ):
        super().__init__(message)
        self.node_id = node_id
        self.node_input_snapshot = node_input_snapshot or {}
        self.stack_trace = stack_trace or traceback.format_exc()

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:
    START = None  # type: ignore[misc, assignment]
    END = None  # type: ignore[misc, assignment]
    StateGraph = None  # type: ignore[misc, assignment]


class WorkflowState(TypedDict, total=False):
    """State passed through the workflow graph."""

    input: dict[str, Any]
    steps: list[dict[str, Any]]
    last_output: str


def _make_nanobot_node(
    agent: "AgentLoop",
    node_id: str,
    node_name: str,
    prompt: str,
    run_id: str,
    workflow_name: str,
) -> Any:
    """Return an async node function that calls run_nanobot_node and updates state."""

    async def _node(state: WorkflowState) -> dict[str, Any]:
        ctx = RuntimeContext(
            run_id=run_id,
            workflow_name=workflow_name,
            node_name=node_name or node_id,
        )
        steps = list(state.get("steps") or [])
        state_dict = dict(state)
        try:
            output = await run_nanobot_node(agent, prompt, state_dict, ctx)
        except Exception as e:
            raise NodeExecutionError(
                node_id=node_id,
                message=str(e),
                node_input_snapshot={
                    "input": state_dict.get("input"),
                    "steps_count": len(steps),
                    "last_output": state_dict.get("last_output", ""),
                },
                stack_trace=traceback.format_exc(),
            ) from e
        steps.append({"node_id": node_id, "node_name": node_name, "output": output})
        return {"steps": steps, "last_output": output}

    return _node


def build_graph(
    definition: dict[str, Any],
    agent: "AgentLoop",
    run_id: str,
    data_dir: Path,
) -> Any:
    """
    Build a compiled LangGraph from a workflow definition.

    Definition must have "nodes" (list of {id, name, type, prompt}) and
    "edges" (list of {from, to}). Node type "nanobot" uses the agent.
    """
    if StateGraph is None:
        raise RuntimeError("langgraph is not installed. pip install langgraph>=1.0.9")

    workflow_name = definition.get("name") or definition.get("id") or "workflow"
    nodes_cfg = definition.get("nodes") or []
    edges_cfg = definition.get("edges") or []

    graph = StateGraph(WorkflowState)

    for n in nodes_cfg:
        node_id = n.get("id") or ""
        node_name = n.get("name") or node_id
        node_type = n.get("type") or "nanobot"
        prompt = n.get("prompt") or "Process the current state and respond."
        if node_type == "nanobot":
            graph.add_node(
                node_id,
                _make_nanobot_node(
                    agent, node_id, node_name, prompt, run_id, workflow_name
                ),
            )
        else:
            # Simple pass-through node (e.g. "function" with no handler)
            def _make_passthrough(nid: str, nname: str) -> Any:
                async def _node(state: WorkflowState) -> dict[str, Any]:
                    steps = list(state.get("steps") or [])
                    steps.append({
                        "node_id": nid,
                        "node_name": nname,
                        "output": state.get("last_output", ""),
                    })
                    return {"steps": steps}
                return _node
            graph.add_node(node_id, _make_passthrough(node_id, node_name))

    # Entry: node(s) that no edge points to (never in "to").
    node_ids = {n.get("id") for n in nodes_cfg if n.get("id")}
    to_ids = {e.get("to") for e in edges_cfg if e.get("to")}
    entry_nodes = node_ids - to_ids
    if not entry_nodes and nodes_cfg:
        first_id = nodes_cfg[0].get("id") if nodes_cfg else None
        entry_nodes = {first_id} if first_id else set()
    for en in entry_nodes:
        if en and en not in ("__end__", "END"):
            graph.add_edge(START, en)

    # Edges between nodes and to END
    for e in edges_cfg:
        from_node = e.get("from")
        to_node = e.get("to")
        if not from_node or not to_node:
            continue
        if to_node == "__end__" or to_node == "END":
            graph.add_edge(from_node, END)
        else:
            graph.add_edge(from_node, to_node)

    # If any node has no outgoing edge, connect to END (for linear chains)
    nodes_with_outgoing = {e.get("from") for e in edges_cfg}
    for n in nodes_cfg:
        nid = n.get("id")
        if nid and nid not in nodes_with_outgoing:
            try:
                graph.add_edge(nid, END)
            except Exception:
                pass

    return graph.compile()


async def run_graph(
    definition: dict[str, Any],
    agent: "AgentLoop",
    run_id: str,
    data_dir: Path,
    input_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Run the workflow graph and return the final state.

    Caller is responsible for create_run/update_run_finished.
    """
    compiled = build_graph(definition, agent, run_id, data_dir)
    initial: WorkflowState = {
        "input": input_payload or {},
        "steps": [],
        "last_output": "",
    }
    result = await compiled.ainvoke(initial)
    return dict(result)
