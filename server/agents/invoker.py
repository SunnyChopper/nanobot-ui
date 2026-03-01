"""
Nanobot node invoker: runs one reasoning step of a LangGraph workflow.

Uses the existing AgentLoop.process_direct API with a synthesized user
message (node prompt + graph state). No changes to nanobot core required.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

from server.agents.context import RuntimeContext

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop


async def run_nanobot_node(
    agent: "AgentLoop",
    node_prompt: str,
    state: dict[str, Any] | None,
    runtime_context: RuntimeContext,
    *,
    max_state_chars: int = 4000,
) -> str:
    """
    Execute one "reasoning" node by invoking nanobot with node prompt and state.

    Args:
        agent: The nanobot AgentLoop (must have MCP connected if tools are needed).
        node_prompt: Instruction for this node (what the model should do).
        state: Current graph state to include as context (serialized into the message).
        runtime_context: Run ID, workflow name, session key, credentials.
        max_state_chars: Cap length of serialized state in the message.

    Returns:
        The agent's response text (to be merged into graph state or parsed as output).
    """
    runtime_context.node_name = runtime_context.node_name or "node"
    session_key = runtime_context.session_key or f"workflow:{runtime_context.run_id}"

    state_blob = ""
    if state:
        try:
            raw = json.dumps(state, default=str)
            state_blob = raw[:max_state_chars] if len(raw) > max_state_chars else raw
        except Exception as e:
            logger.warning(f"Workflow {runtime_context.workflow_name} run {runtime_context.run_id}: could not serialize state: {e}")

    if state_blob:
        content = f"{node_prompt}\n\n---\nCurrent graph state (JSON):\n```json\n{state_blob}\n```"
    else:
        content = node_prompt

    logger.info(
        f"Workflow {runtime_context.workflow_name} run {runtime_context.run_id}: "
        f"invoking nanobot for node {runtime_context.node_name}"
    )
    response = await agent.process_direct(
        content,
        session_key=session_key,
        channel="workflow",
        chat_id=runtime_context.run_id,
    )
    return response or ""
