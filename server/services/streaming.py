"""
Token-streaming agent loop for the nanobot web server.

Implements a streaming version of AgentLoop._run_agent_loop() that emits
WebSocket events for each token, tool call, and tool result.

This module calls litellm.acompletion(stream=True) directly. LiteLLMProvider
already configures the litellm globals and environment variables during its
__init__(), so once a provider is constructed any direct litellm call will
use the correct credentials.

No nanobot source files are modified.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import json_repair
from litellm import acompletion
from loguru import logger

from nanobot.agent.bus import bus
from nanobot.agent.tools.desktop import SCREENSHOT_RESULT_PREFIX
from server import hooks
from server.circuit_breaker import CircuitOpenError, get_circuit_breaker
from server.constants.streaming import (
    BLOCK_APPROVAL_REQUEST,
    BLOCK_CONTENT,
    BLOCK_THINKING,
    BLOCK_TOOL_CALL,
    CIRCUIT_BREAKER_MESSAGE,
    EVENT_ERROR,
    EVENT_THINKING,
    EVENT_TOKEN,
    EVENT_TOOL_APPROVAL_REQUEST,
    EVENT_TOOL_CALL,
    EVENT_TOOL_PROGRESS,
    EVENT_TOOL_RESULT,
    KEY_ARGUMENTS,
    KEY_CONTENT,
    KEY_DENIED,
    KEY_NAME,
    KEY_REQUEST,
    KEY_RESOLVED,
    KEY_RESULT,
    KEY_TEXT,
    KEY_TITLE,
    KEY_TOOL_CALL,
    KEY_TOOL_ID,
    KEY_TYPE,
    POLICY_ASK,
    POLICY_AUTO,
    POLICY_DENY,
    REFLECT_USER_MESSAGE,
    TOOL_CALL_TYPE_FUNCTION,
    TOOL_CHUNK_ID_PREFIX,
)
from server.models import StreamAgentLoopParams, StreamAgentLoopResult

# ---------------------------------------------------------------------------
# Tool policy helpers
# ---------------------------------------------------------------------------

# Default policy for tools not listed in the user's config.
_DEFAULT_POLICY: dict[str, str] = {
    "read_file": POLICY_AUTO,
    "list_dir": POLICY_AUTO,
    "web_search": POLICY_AUTO,
    "web_fetch": POLICY_AUTO,
    "message": POLICY_AUTO,
    "system_stats": POLICY_AUTO,
    "semantic_search": POLICY_AUTO,
    "rag_ingest": POLICY_ASK,
    "mouse_move": POLICY_ASK,
    "mouse_click": POLICY_ASK,
    "mouse_position": POLICY_ASK,
    "keyboard_type": POLICY_ASK,
    "screenshot": POLICY_ASK,
    "screenshot_region": POLICY_ASK,
    "locate_on_screen": POLICY_ASK,
    "click_image": POLICY_ASK,
    "write_file": POLICY_ASK,
    "edit_file": POLICY_ASK,
    "exec": POLICY_ASK,
    "run_python": POLICY_ASK,
    "spawn": POLICY_ASK,
    "cron": POLICY_ASK,
}


def _resolve_tool_policy(tool_name: str, user_policy: dict[str, str]) -> str:
    """Return effective policy for a tool: user override > default > mcp fallback."""
    if tool_name in user_policy:
        return user_policy[tool_name]
    if tool_name in _DEFAULT_POLICY:
        return _DEFAULT_POLICY[tool_name]
    # MCP tools (mcp_<server>_<tool>) are unknown — default to "ask"
    if tool_name.startswith("mcp_"):
        return POLICY_ASK
    return POLICY_AUTO


async def stream_agent_loop(params: StreamAgentLoopParams) -> StreamAgentLoopResult:
    """
    Run the agent loop with streaming token output.

    Mirrors AgentLoop._run_agent_loop() but emits structured events via
    on_event() for each token delta, tool call, and tool result.

    Uses nanobot's ContextBuilder, ToolRegistry, and Session via their
    public APIs -- no subclassing or monkey-patching required.

    Returns:
        StreamAgentLoopResult with final_content and tools_used.
    """
    context_builder = params.context_builder
    session = params.session
    tool_registry = params.tool_registry
    model = params.model
    temperature = params.temperature
    max_tokens = params.max_tokens
    max_iterations = params.max_iterations
    memory_window = params.memory_window
    user_message = params.user_message
    on_event = params.on_event
    channel = params.channel
    chat_id = params.chat_id
    media = params.media
    api_key = params.api_key
    api_base = params.api_base
    extra_headers = params.extra_headers
    reasoning_effort = getattr(params, "reasoning_effort", None)
    tool_policy = params.tool_policy
    request_approval = params.request_approval
    generate_approval_title = params.generate_approval_title
    is_allowlisted = params.is_allowlisted
    max_llm_retries = params.max_llm_retries
    retry_backoff_base_seconds = params.retry_backoff_base_seconds
    circuit_breaker_failure_threshold = params.circuit_breaker_failure_threshold
    circuit_breaker_recovery_seconds = params.circuit_breaker_recovery_seconds
    collected_blocks = params.collected_blocks
    tool_timeout_seconds = getattr(params, "tool_timeout_seconds", 0) or 0
    cua_auto_approve = getattr(params, "cua_auto_approve", False)
    cua_safety_model = getattr(params, "cua_safety_model", "") or "llama-3.1-8b-instant"
    cua_safety_api_key = getattr(params, "cua_safety_api_key", None)

    messages = context_builder.build_messages(
        history=session.get_history(max_messages=memory_window),
        current_message=user_message,
        channel=channel,
        chat_id=chat_id,
        media=media,
    )
    tools_used: list[str] = []
    final_content: str | None = None

    async def _on_event(ev: dict[str, Any]) -> None:
        if collected_blocks is not None:
            t = ev.get(KEY_TYPE)
            if t == EVENT_THINKING:
                c = ev.get(KEY_CONTENT, "")
                if collected_blocks and collected_blocks[-1].get(KEY_TYPE) == BLOCK_THINKING:
                    collected_blocks[-1][KEY_TEXT] += c
                else:
                    collected_blocks.append({KEY_TYPE: BLOCK_THINKING, KEY_TEXT: c, "collapsed": True})
            elif t == EVENT_TOOL_CALL:
                collected_blocks.append({
                    KEY_TYPE: BLOCK_TOOL_CALL,
                    KEY_TOOL_CALL: {
                        KEY_NAME: ev[KEY_NAME],
                        KEY_ARGUMENTS: ev.get(KEY_ARGUMENTS, {}),
                        KEY_TOOL_ID: ev.get(KEY_TOOL_ID),
                    },
                })
            elif t == EVENT_TOOL_RESULT:
                tid = ev.get(KEY_TOOL_ID)
                for i in range(len(collected_blocks) - 1, -1, -1):
                    b = collected_blocks[i]
                    if b.get(KEY_TYPE) == BLOCK_TOOL_CALL:
                        tc = b.get(KEY_TOOL_CALL, {})
                        if tc.get(KEY_TOOL_ID) == tid:
                            tc[KEY_RESULT] = ev.get(KEY_RESULT, "")
                            break
            elif t == EVENT_TOOL_PROGRESS:
                tid = ev.get(KEY_TOOL_ID)
                for i in range(len(collected_blocks) - 1, -1, -1):
                    b = collected_blocks[i]
                    if b.get(KEY_TYPE) == BLOCK_TOOL_CALL:
                        tc = b.get(KEY_TOOL_CALL, {})
                        if tc.get(KEY_TOOL_ID) == tid:
                            tc["progress"] = ev.get(KEY_CONTENT, "")
                            break
            elif t == EVENT_TOOL_APPROVAL_REQUEST:
                req: dict[str, Any] = {
                    KEY_TOOL_ID: ev[KEY_TOOL_ID],
                    KEY_NAME: ev[KEY_NAME],
                    KEY_ARGUMENTS: ev.get(KEY_ARGUMENTS, {}),
                }
                if ev.get(KEY_TITLE):
                    req[KEY_TITLE] = ev[KEY_TITLE]
                collected_blocks.append({
                    KEY_TYPE: BLOCK_APPROVAL_REQUEST,
                    KEY_REQUEST: req,
                    KEY_RESOLVED: None,
                })
        await on_event(ev)

    event_sink = _on_event if collected_blocks is not None else on_event

    # Subscribe to side-car events (like screenshots) from tools
    async def bus_callback(event: dict[str, Any]):
        await on_event(event)

    bus.subscribe(bus_callback)

    breaker = get_circuit_breaker(
        failure_threshold=circuit_breaker_failure_threshold,
        recovery_seconds=circuit_breaker_recovery_seconds,
    )

    try:
        for iteration in range(max_iterations):
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": max(1, max_tokens),
                "temperature": temperature,
                "stream": True,
            }
            if api_key:
                kwargs["api_key"] = api_key
            if api_base:
                kwargs["api_base"] = api_base
            if extra_headers:
                kwargs["extra_headers"] = extra_headers
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

            tool_defs = tool_registry.get_definitions()
            if tool_defs:
                kwargs["tools"] = tool_defs
                kwargs["tool_choice"] = "auto"

            async def _one_stream_attempt() -> tuple[str, dict[int, dict[str, str]]]:
                stream = await acompletion(**kwargs)
                collected_content = ""
                tool_call_chunks: dict[int, dict[str, str]] = {}
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    # Thinking/reasoning visibility is model-dependent (e.g. Claude extended thinking, DeepSeek-R1).
                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        await event_sink({KEY_TYPE: EVENT_THINKING, KEY_CONTENT: reasoning})
                    if delta.content:
                        collected_content += delta.content
                        await event_sink({KEY_TYPE: EVENT_TOKEN, KEY_CONTENT: delta.content})
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_call_chunks:
                                tool_call_chunks[idx] = {"id": "", "name": "", "args": ""}
                            entry = tool_call_chunks[idx]
                            if tc_delta.id:
                                entry["id"] += tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    entry["name"] += tc_delta.function.name
                                if tc_delta.function.arguments:
                                    entry["args"] += tc_delta.function.arguments
                return collected_content, tool_call_chunks

            stream_succeeded = False
            for attempt in range(max_llm_retries):
                try:
                    collected_content, tool_call_chunks = await breaker.call(_one_stream_attempt)
                    stream_succeeded = True
                    break
                except CircuitOpenError:
                    logger.warning("LLM call rejected: circuit breaker is open")
                    await event_sink({
                        KEY_TYPE: EVENT_ERROR,
                        KEY_CONTENT: CIRCUIT_BREAKER_MESSAGE,
                    })
                    return StreamAgentLoopResult(final_content=None, tools_used=tools_used)
                except Exception as exc:
                    if attempt < max_llm_retries - 1:
                        wait_s = retry_backoff_base_seconds * (2 ** attempt)
                        logger.warning(
                            f"LLM stream error (iteration {iteration + 1}, "
                            f"attempt {attempt + 1}/{max_llm_retries}), "
                            f"retrying in {wait_s}s: {exc}"
                        )
                        await event_sink({
                            KEY_TYPE: EVENT_TOKEN,
                            KEY_CONTENT: f"\n\n_Retrying… (attempt {attempt + 2}/{max_llm_retries})_\n\n",
                        })
                        await asyncio.sleep(wait_s)
                    else:
                        logger.error(
                            f"LLM stream error after {max_llm_retries} attempts "
                            f"(iteration {iteration + 1}): {exc}"
                        )
                        await event_sink({KEY_TYPE: EVENT_ERROR, KEY_CONTENT: str(exc)})
                        return StreamAgentLoopResult(final_content=None, tools_used=tools_used)

            if not stream_succeeded:
                return StreamAgentLoopResult(final_content=None, tools_used=tools_used)

            # Parse accumulated tool calls and emit in order (content was already streamed)
            parsed_tool_calls = []
            for idx in sorted(tool_call_chunks):
                entry = tool_call_chunks[idx]
                if not entry["name"]:
                    continue
                try:
                    args = json_repair.loads(entry["args"]) if entry["args"] else {}
                except Exception:
                    args = {}
                parsed_tool_calls.append({
                    "id": entry["id"] or f"{TOOL_CHUNK_ID_PREFIX}{idx}",
                    KEY_NAME: entry[KEY_NAME],
                    KEY_ARGUMENTS: args,
                })

            # Ensure newline between content and tool output for formatting
            if parsed_tool_calls and collected_content and not collected_content.endswith("\n"):
                await event_sink({KEY_TYPE: EVENT_TOKEN, KEY_CONTENT: "\n"})

            # Persist content segment before tool calls (or final content if no tools)
            if collected_blocks is not None and collected_content:
                collected_blocks.append({KEY_TYPE: BLOCK_CONTENT, KEY_TEXT: collected_content})

            if parsed_tool_calls:
                # Build assistant message with tool calls (mirrors context_builder.add_assistant_message)
                tool_call_dicts = [
                    {
                        "id": tc["id"],
                        KEY_TYPE: TOOL_CALL_TYPE_FUNCTION,
                        "function": {
                            KEY_NAME: tc[KEY_NAME],
                            KEY_ARGUMENTS: json.dumps(tc[KEY_ARGUMENTS]),
                        },
                    }
                    for tc in parsed_tool_calls
                ]
                messages = context_builder.add_assistant_message(
                    messages, collected_content or None, tool_call_dicts
                )

                # Execute each tool and emit events (chronological order after content)
                for tc in parsed_tool_calls:
                    tool_name = tc[KEY_NAME]
                    tool_args = tc[KEY_ARGUMENTS]
                    tool_id = tc["id"]

                    args_preview = json.dumps(tool_args, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_name}({args_preview[:200]})")

                    # Check tool policy before executing
                    effective_policy = tool_policy or {}
                    policy = _resolve_tool_policy(tool_name, effective_policy)
                    if cua_auto_approve and tool_name in (
    "screenshot", "screenshot_region", "mouse_move", "mouse_click", "mouse_position", "keyboard_type",
    "locate_on_screen", "click_image", "get_foreground_window", "launch_app",
):
                        policy = POLICY_AUTO

                    if policy == POLICY_DENY:
                        denied_result = f"Tool '{tool_name}' is blocked by policy (denied)."
                        logger.info(f"Tool blocked by deny policy: {tool_name}")
                        await event_sink({
                            KEY_TYPE: EVENT_TOOL_CALL,
                            KEY_NAME: tool_name,
                            KEY_ARGUMENTS: tool_args,
                            KEY_TOOL_ID: tool_id,
                            KEY_DENIED: True,
                        })
                        await event_sink({
                            KEY_TYPE: EVENT_TOOL_RESULT,
                            KEY_NAME: tool_name,
                            KEY_RESULT: denied_result,
                            KEY_TOOL_ID: tool_id,
                        })
                        messages = context_builder.add_tool_result(
                            messages, tool_id, tool_name, denied_result
                        )
                        continue

                    if policy == POLICY_ASK:
                        approved = False
                        deny_reason: str | None = None
                        if is_allowlisted is not None:
                            try:
                                if await is_allowlisted(tool_name, tool_args):
                                    approved = True
                            except Exception:
                                pass
                        if not approved and tool_name == "run_python" and cua_auto_approve and cua_safety_api_key:
                            from server.cua_safety import is_safe_python_for_cua
                            code = (tool_args.get("code") or "").strip()
                            if code and await is_safe_python_for_cua(code, cua_safety_model, cua_safety_api_key):
                                approved = True
                        if not approved and request_approval is not None:
                            approval_event: dict[str, Any] = {
                                KEY_TYPE: EVENT_TOOL_APPROVAL_REQUEST,
                                KEY_NAME: tool_name,
                                KEY_ARGUMENTS: tool_args,
                                KEY_TOOL_ID: tool_id,
                            }
                            if generate_approval_title is not None:
                                try:
                                    title = await generate_approval_title(tool_name, tool_args)
                                    if title and str(title).strip():
                                        approval_event[KEY_TITLE] = str(title).strip()
                                except Exception as e:
                                    logger.debug(f"Approval title generation skipped: {e}")
                            await event_sink(approval_event)
                            approval_result = await request_approval(tool_name, tool_args, tool_id)
                            approved = approval_result[0] if isinstance(approval_result, tuple) else bool(approval_result)
                            deny_reason = approval_result[1] if isinstance(approval_result, tuple) and len(approval_result) > 1 else None
                            if collected_blocks and collected_blocks[-1].get(KEY_TYPE) == BLOCK_APPROVAL_REQUEST:
                                collected_blocks[-1][KEY_RESOLVED] = "approved" if approved else "denied"
                        if not approved:
                            denied_result = f"Tool '{tool_name}' was denied by the user."
                            if deny_reason and deny_reason.strip():
                                denied_result += f" User feedback: {deny_reason.strip()}"
                            logger.info(f"Tool denied by user: {tool_name}")
                            await event_sink({
                                KEY_TYPE: EVENT_TOOL_RESULT,
                                KEY_NAME: tool_name,
                                KEY_RESULT: denied_result,
                                KEY_TOOL_ID: tool_id,
                            })
                            messages = context_builder.add_tool_result(
                                messages, tool_id, tool_name, denied_result
                            )
                            continue

                    tools_used.append(tool_name)
                    await event_sink({
                        KEY_TYPE: EVENT_TOOL_CALL,
                        KEY_NAME: tool_name,
                        KEY_ARGUMENTS: tool_args,
                        KEY_TOOL_ID: tool_id,
                    })

                    async def progress_callback(message: str) -> None:
                        await event_sink({
                            KEY_TYPE: EVENT_TOOL_PROGRESS,
                            KEY_TOOL_ID: tool_id,
                            KEY_CONTENT: message,
                        })

                    await hooks.run_before_tool_call(tool_name, tool_args)
                    try:
                        if tool_timeout_seconds > 0:
                            result = await asyncio.wait_for(
                                tool_registry.execute(
                                    tool_name,
                                    tool_args,
                                    progress_callback=progress_callback,
                                ),
                                timeout=tool_timeout_seconds,
                            )
                        else:
                            result = await tool_registry.execute(
                                tool_name,
                                tool_args,
                                progress_callback=progress_callback,
                            )
                        await hooks.run_after_tool_call(tool_name, tool_args, result, None)
                    except asyncio.TimeoutError:
                        result = f"Tool execution timed out after {tool_timeout_seconds} seconds."
                        await hooks.run_after_tool_call(tool_name, tool_args, result, None)
                    except Exception as e:
                        err_msg = str(e)
                        await hooks.run_after_tool_call(tool_name, tool_args, "", err_msg)
                        raise

                    # Screenshot tool returns SCREENSHOT_RESULT_PREFIX + base64; inject image for the model.
                    if tool_name == "screenshot" and result.startswith(SCREENSHOT_RESULT_PREFIX):
                        b64 = result[len(SCREENSHOT_RESULT_PREFIX) :]
                        short_result = (
                            "Screenshot attached below. Use the coordinate overlay in the image "
                            "to choose (x,y) for mouse_click."
                        )
                        await event_sink({
                            KEY_TYPE: EVENT_TOOL_RESULT,
                            KEY_NAME: tool_name,
                            KEY_RESULT: short_result,
                            KEY_TOOL_ID: tool_id,
                        })
                        messages = context_builder.add_tool_result(
                            messages, tool_id, tool_name, short_result
                        )
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                                {"type": "text", "text": "Screenshot above. Use the coordinate overlay to choose (x,y) for mouse_click."},
                            ],
                        })
                    else:
                        await event_sink({
                            KEY_TYPE: EVENT_TOOL_RESULT,
                            KEY_NAME: tool_name,
                            KEY_RESULT: result[:1000],
                            KEY_TOOL_ID: tool_id,
                        })
                        messages = context_builder.add_tool_result(
                            messages, tool_id, tool_name, result
                        )

                messages.append({
                    "role": "user",
                    "content": REFLECT_USER_MESSAGE,
                })

            else:
                # No tool calls -- this is the final response
                final_content = collected_content or None
                break

    finally:
        bus.unsubscribe(bus_callback)

    return StreamAgentLoopResult(final_content=final_content, tools_used=tools_used)
