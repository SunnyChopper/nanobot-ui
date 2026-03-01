"""
WebSocket handler for real-time streaming chat.

Manages WebSocket connections, routes incoming client frames to the streaming
agent loop, and relays events back to the connected browser tab.

Key design: a background `frame_reader` task continuously reads raw WS frames
into an `asyncio.Queue`. The main loop processes frames from the queue.
This lets streaming tasks run concurrently with incoming frames (approvals,
pings) without blocking each other.

Each browser tab connects with a session_id (UUID stored in localStorage).
The session_id maps to a nanobot session key of the form 'web:<session_id>'.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket, WebSocketDisconnect
from litellm import acompletion
from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.providers.litellm_provider import ensure_provider_env, resolve_model
from nanobot.session.manager import SessionManager
from server import allowlist as allowlist_module
from server import hooks
from server.memory import run_immediate_memory
from server.models import StreamAgentLoopParams
from server.services.streaming import stream_agent_loop

if TYPE_CHECKING:
    from nanobot.config.schema import Config


class ConnectionRegistry:
    """Track active WebSocket connections by session_id."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[session_id] = ws
        logger.info(f"WebSocket connected: session={session_id} (total={len(self._connections)})")

    def reregister(self, old_id: str, new_id: str, ws: WebSocket) -> None:
        """Move an already-accepted connection to a new session_id without re-accepting."""
        self._connections.pop(old_id, None)
        self._connections[new_id] = ws

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)
        logger.info(f"WebSocket disconnected: session={session_id}")

    def get(self, session_id: str) -> WebSocket | None:
        return self._connections.get(session_id)

    @property
    def active_count(self) -> int:
        return len(self._connections)


async def websocket_endpoint(
    ws: WebSocket,
    registry: ConnectionRegistry,
    session_manager: SessionManager,
    context_builder: ContextBuilder,
    tool_registry: Any,
    config: "Config",
    agent: Any = None,
) -> None:
    """
    Handle a WebSocket connection for a single browser tab.

    Protocol (JSON frames):

    Client → Server:
        {"type": "message",              "content": "...", "session_id": "..."}
        {"type": "new_session",          "session_id": "..."}
        {"type": "tool_approval_response","tool_id": "...", "approved": true}
        {"type": "ping"}

    Server → Client:
        {"type": "token",                "content": "...",  "session_id": "..."}
        {"type": "thinking",             "content": "..."}  # reasoning stream (Claude, Deepseek, etc.)
        {"type": "tool_call",            "name": "...", "arguments": {...},  "session_id": "...", "tool_id": "..."}
        {"type": "tool_approval_request","name": "...", "arguments": {...},  "session_id": "...", "tool_id": "..."}
        {"type": "tool_result",          "name": "...", "result": "...",     "session_id": "...", "tool_id": "..."}
        {"type": "message_complete",     "content": "...", "session_id": "...", "tools_used": [...]}
        {"type": "error",                "content": "..."}
        {"type": "pong"}
        {"type": "session_ready",        "session_id": "..."}
        {"type": "assistant_message",    "session_id": "...", "content": "..."}  # async callback (e.g. subagent done)
    """
    # Assign a temporary session_id until the client sends one
    temp_id = str(uuid.uuid4())
    await registry.connect(temp_id, ws)
    active_session_id: str = temp_id

    # Derive LLM credentials from config for the streaming loop
    raw_model = (config.agents.defaults.model or "").strip()
    if not raw_model:
        raw_model = "anthropic/claude-opus-4-5"  # fallback so LiteLLM always gets a valid model
    provider_name = config.get_provider_name(raw_model)
    p = config.get_provider(raw_model)
    api_key = p.api_key if p else None
    api_base = config.get_api_base(raw_model)
    extra_headers = p.extra_headers if p else None
    # Resolve to a litellm-routable model (e.g. gemini-3-pro-preview -> gemini/gemini-3-pro-preview)
    model = resolve_model(raw_model, provider_name=provider_name, api_key=api_key, api_base=api_base)
    ensure_provider_env(model, provider_name, api_key, api_base)

    async def send_event(event: dict[str, Any]) -> None:
        """Send a JSON frame to this WebSocket connection."""
        try:
            await ws.send_text(json.dumps(event))
        except Exception:
            pass  # Connection may have closed mid-stream

    # ---------------------------------------------------------------------------
    # Concurrent infrastructure
    # ---------------------------------------------------------------------------

    # Queue for all incoming WS frames (written by frame_reader, read by main loop)
    incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    # Pending tool-approval futures: tool_id → Future[(approved, reason)]
    approval_futures: dict[str, asyncio.Future[tuple[bool, str | None]]] = {}

    async def frame_reader() -> None:
        """Background task: read raw WS frames into the queue."""
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    frame = {"type": "error_internal"}
                await incoming.put(frame)
        except WebSocketDisconnect:
            await incoming.put({"type": "__disconnect__"})
        except Exception as exc:
            logger.error(f"Frame reader error for session {active_session_id}: {exc}")
            await incoming.put({"type": "__disconnect__"})

    reader_task = asyncio.create_task(frame_reader())
    current_stream_task: asyncio.Task[None] | None = None
    # Message queue: list of {content, session_id, media_paths, queue_id, attachment_paths_raw}
    message_queue: list[dict[str, Any]] = []

    def _emit_queue_updated() -> None:
        """Emit queue_updated event with current queue_ids and count."""
        queue_ids = [item.get("queue_id") for item in message_queue if item.get("queue_id")]
        asyncio.create_task(
            send_event({"type": "queue_updated", "session_id": active_session_id, "queue_ids": queue_ids, "count": len(message_queue)})
        )

    def _start_stream(payload: dict[str, Any]) -> asyncio.Task[None]:
        """Start a single stream for the given payload. On completion, pops next from message_queue if any."""
        nonlocal current_stream_task
        _content = payload["content"]
        _active_sid = payload["session_id"]
        _session = session_manager.get_or_create(f"web:{_active_sid}")
        _media_paths = payload.get("media_paths") or []

        async def on_event(event: dict[str, Any]) -> None:
            event["session_id"] = _active_sid
            await send_event(event)

        async def is_allowlisted_cb(tool_name: str, tool_args: dict[str, Any]) -> bool:
            return allowlist_module.is_allowlisted(tool_name, tool_args)

        async def approval_callback(
            tool_name: str,
            tool_args: dict[str, Any],
            tool_id: str,
        ) -> tuple[bool, str | None]:
            loop = asyncio.get_event_loop()
            fut: asyncio.Future[tuple[bool, str | None]] = loop.create_future()
            approval_futures[tool_id] = fut
            try:
                return await fut
            finally:
                approval_futures.pop(tool_id, None)

        async def generate_approval_title(tool_name: str, tool_args: dict[str, Any]) -> str:
            try:
                args_preview = json.dumps(tool_args, ensure_ascii=False)[:500]
                response = await acompletion(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                "Summarize this tool request in one short phrase "
                                "(e.g. 'Run shell command: bw status' or 'Edit file src/main.py'). "
                                "Reply with only the phrase, no quotes or punctuation.\n\n"
                                f"Tool: {tool_name}\nArguments: {args_preview}"
                            ),
                        }
                    ],
                    max_tokens=60,
                    temperature=0,
                    api_key=api_key,
                    api_base=api_base,
                    extra_headers=extra_headers,
                )
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.debug(f"Approval title generation failed: {e}")
            return ""

        collected_blocks: list[dict[str, Any]] = []

        async def run_stream() -> None:
            nonlocal current_stream_task
            try:
                if agent is not None:
                    agent._set_tool_context("web", _active_sid)
                params = StreamAgentLoopParams(
                    context_builder=context_builder,
                    session=_session,
                    tool_registry=tool_registry,
                    model=model,
                    temperature=config.agents.defaults.temperature,
                    max_tokens=config.agents.defaults.max_tokens,
                    max_iterations=config.agents.defaults.max_tool_iterations,
                    memory_window=config.agents.defaults.memory_window,
                    user_message=_content,
                    on_event=on_event,
                    channel="web",
                    chat_id=_active_sid,
                    media=_media_paths if _media_paths else None,
                    api_key=api_key,
                    api_base=api_base,
                    extra_headers=extra_headers,
                    tool_policy=dict(config.tools.tool_policy),
                    request_approval=approval_callback,
                    generate_approval_title=generate_approval_title,
                    is_allowlisted=is_allowlisted_cb,
                    max_llm_retries=getattr(config.agents.defaults, "max_llm_retries", 3),
                    retry_backoff_base_seconds=getattr(config.agents.defaults, "retry_backoff_base_seconds", 2),
                    circuit_breaker_failure_threshold=getattr(config.gateway, "circuit_breaker_failure_threshold", 5),
                    circuit_breaker_recovery_seconds=getattr(config.gateway, "circuit_breaker_recovery_seconds", 60.0),
                    tool_timeout_seconds=getattr(config.tools, "tool_timeout_seconds", 0) or 0,
                    collected_blocks=collected_blocks,
                    cua_auto_approve=getattr(config.tools, "cua_auto_approve", False),
                    cua_safety_model=getattr(config.tools, "cua_safety_model", "") or "llama-3.1-8b-instant",
                    cua_safety_api_key=getattr(getattr(config.providers, "groq", None), "api_key", None) or None,
                )
                result = await stream_agent_loop(params)

                final_content = result.final_content
                tools_used = result.tools_used
                if final_content is None:
                    final_content = "I've completed processing but have no response to give."

                _session.add_message("user", _content)
                _session.add_message(
                    "assistant",
                    final_content,
                    tools_used=tools_used if tools_used else None,
                    blocks=collected_blocks if collected_blocks else None,
                )

                if not _session.metadata.get("title"):
                    title = _content[:60].strip()
                    if len(_content) > 60:
                        title += "…"
                    _session.metadata["title"] = title

                session_manager.save(_session)

                memory_model = (getattr(config.agents.defaults, "memory_model", None) or "").strip()
                if memory_model and len(_session.messages) >= 2:
                    last_messages = _session.messages[-2:]
                    asyncio.create_task(
                        run_immediate_memory(config.workspace_path, config, last_messages)
                    )

                await hooks.run_after_response(
                    _active_sid,
                    final_content,
                    tools_used,
                )

                await send_event({
                    "type": "message_complete",
                    "content": final_content,
                    "session_id": _active_sid,
                    "tools_used": tools_used,
                })

                # Process next message from queue if any (not on cancel)
                if message_queue:
                    next_payload = message_queue.pop(0)
                    _emit_queue_updated()
                    current_stream_task = _start_stream(next_payload)

            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error(f"Agent loop error for session {_active_sid}: {exc}")
                await send_event({
                    "type": "error",
                    "content": f"Agent error: {str(exc)}",
                    "session_id": _active_sid,
                })
                # Process next message from queue if any
                if message_queue:
                    next_payload = message_queue.pop(0)
                    _emit_queue_updated()
                    current_stream_task = _start_stream(next_payload)

        return asyncio.create_task(run_stream())

    # ---------------------------------------------------------------------------
    # Main processing loop
    # ---------------------------------------------------------------------------

    try:
        while True:
            frame = await incoming.get()

            msg_type = frame.get("type", "")

            # -------------------------------------------------------------------
            # Lifecycle / meta frames
            # -------------------------------------------------------------------

            if msg_type == "__disconnect__":
                break

            if msg_type == "ping":
                await send_event({"type": "pong"})
                continue

            # -------------------------------------------------------------------
            # Interrupt: cancel current stream without starting a new one
            # -------------------------------------------------------------------

            if msg_type == "interrupt":
                if current_stream_task and not current_stream_task.done():
                    current_stream_task.cancel()
                    try:
                        await current_stream_task
                    except (asyncio.CancelledError, Exception):
                        pass
                    current_stream_task = None
                await send_event({
                    "type": "interrupt_ack",
                    "session_id": active_session_id,
                })
                continue

            # -------------------------------------------------------------------
            # Tool approval response (arrives while streaming awaits approval)
            # -------------------------------------------------------------------

            if msg_type == "tool_approval_response":
                tool_id = frame.get("tool_id", "")
                approved = bool(frame.get("approved", False))
                reason: str | None = (frame.get("reason") or "").strip() or None
                fut = approval_futures.get(tool_id)
                if fut and not fut.done():
                    fut.set_result((approved, reason))
                continue

            # -------------------------------------------------------------------
            # Session setup: client sends its persisted session_id
            # -------------------------------------------------------------------

            if msg_type == "session_init":
                client_session_id = frame.get("session_id") or str(uuid.uuid4())
                registry.reregister(active_session_id, client_session_id, ws)
                active_session_id = client_session_id
                await send_event({
                    "type": "session_ready",
                    "session_id": active_session_id,
                })
                continue

            # -------------------------------------------------------------------
            # New session: clear history and start fresh
            # -------------------------------------------------------------------

            if msg_type == "new_session":
                if frame.get("session_id"):
                    new_sid = frame["session_id"]
                    registry.reregister(active_session_id, new_sid, ws)
                    active_session_id = new_sid

                session_key = f"web:{active_session_id}"
                session = session_manager.get_or_create(session_key)
                session.clear()
                session_manager.save(session)
                message_queue.clear()
                _emit_queue_updated()
                await send_event({
                    "type": "session_ready",
                    "session_id": active_session_id,
                })
                continue

            # -------------------------------------------------------------------
            # Retract: remove a message from the queue by queue_id
            # -------------------------------------------------------------------

            if msg_type == "retract":
                queue_id = frame.get("queue_id") or ""
                if queue_id:
                    message_queue[:] = [item for item in message_queue if item.get("queue_id") != queue_id]
                    _emit_queue_updated()
                continue

            # -------------------------------------------------------------------
            # Run immediately: remove message from queue, cancel current stream, run it
            # -------------------------------------------------------------------

            if msg_type == "run_immediately":
                queue_id = frame.get("queue_id") or ""
                if not queue_id:
                    continue
                # Find and remove the item from queue
                run_payload: dict[str, Any] | None = None
                for i, item in enumerate(message_queue):
                    if item.get("queue_id") == queue_id:
                        run_payload = message_queue.pop(i)
                        break
                if not run_payload:
                    continue
                _emit_queue_updated()
                # Cancel current stream if running
                if current_stream_task and not current_stream_task.done():
                    current_stream_task.cancel()
                    try:
                        await current_stream_task
                    except (asyncio.CancelledError, Exception):
                        pass
                    current_stream_task = None
                # Start stream with this payload (defined below in _start_stream)
                current_stream_task = _start_stream(run_payload)
                continue

            # -------------------------------------------------------------------
            # Chat message: launch the streaming agent loop or enqueue
            # -------------------------------------------------------------------

            if msg_type == "message":
                content = (frame.get("content") or "").strip()
                if not content:
                    await send_event({"type": "error", "content": "Empty message."})
                    continue

                # Allow overriding session from the message frame
                if frame.get("session_id"):
                    active_session_id = frame["session_id"]

                queue_id = frame.get("queue_id") or str(uuid.uuid4())

                session_key = f"web:{active_session_id}"
                session = session_manager.get_or_create(session_key)

                # Resolve attachment paths (from upload API: "media/uuid.ext") to full paths
                from pathlib import Path

                from nanobot.utils.helpers import get_data_path
                attachment_paths_raw = frame.get("attachments") or []
                data_dir = get_data_path().resolve()
                media_paths: list[str] = []
                for p in attachment_paths_raw:
                    if isinstance(p, str) and p and not Path(p).is_absolute():
                        full = (data_dir / p).resolve()
                        if full.exists() and str(full).startswith(str(data_dir)):
                            media_paths.append(str(full))

                # Project context: if session has an active project, prepend PROJECT_CONTEXT.md
                from server.projects import get_project_context_path, load_projects
                project_name = session.metadata.get("project")
                if project_name:
                    projects_map = load_projects(config.workspace_path)
                    project_abs_path = projects_map.get(project_name)
                    if project_abs_path:
                        ctx_path = get_project_context_path(project_abs_path)
                        if ctx_path and ctx_path.is_file():
                            try:
                                project_content = ctx_path.read_text(encoding="utf-8")
                                content = f"## Project context\n\n{project_content}\n\n---\n\n{content}"
                            except (OSError, UnicodeDecodeError):
                                pass

                payload: dict[str, Any] = {
                    "content": content,
                    "session_id": active_session_id,
                    "media_paths": media_paths,
                    "queue_id": queue_id,
                }

                # If stream is running, enqueue; otherwise start stream
                if current_stream_task and not current_stream_task.done():
                    message_queue.append(payload)
                    _emit_queue_updated()
                    continue

                current_stream_task = _start_stream(payload)
                continue

            # Unknown frame type
            await send_event({"type": "error", "content": f"Unknown message type: {msg_type!r}"})

    except Exception as exc:
        logger.error(f"WebSocket error for session {active_session_id}: {exc}")
    finally:
        reader_task.cancel()
        if current_stream_task and not current_stream_task.done():
            current_stream_task.cancel()
        registry.disconnect(active_session_id)
