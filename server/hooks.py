"""
Optional hook registry for the server-side agent flow.

Extensions (or the server itself) can register callbacks that run:
- before_tool_call: (name, arguments) before each tool execution
- after_tool_call: (name, arguments, result, error?) after each tool execution
- after_response: (session_id, content, tools_used) after the full response is done

All callbacks are async and are awaited. Exceptions in a callback are logged
and do not stop the flow. Register at server startup (e.g. in app lifespan or
bootstrap); services/streaming.py and websocket.py invoke these hooks.

No nanobot source files are modified.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from loguru import logger

# Callback types
BeforeToolCall = Callable[[str, dict[str, Any]], Awaitable[None]]
AfterToolCall = Callable[[str, dict[str, Any], str, str | None], Awaitable[None]]
AfterResponse = Callable[[str, str | None, list[str]], Awaitable[None]]

_before_tool_call: list[BeforeToolCall] = []
_after_tool_call: list[AfterToolCall] = []
_after_response: list[AfterResponse] = []


def register_before_tool_call(cb: BeforeToolCall) -> None:
    _before_tool_call.append(cb)


def register_after_tool_call(cb: AfterToolCall) -> None:
    _after_tool_call.append(cb)


def register_after_response(cb: AfterResponse) -> None:
    _after_response.append(cb)


async def run_before_tool_call(name: str, arguments: dict[str, Any]) -> None:
    for cb in _before_tool_call:
        try:
            await cb(name, arguments)
        except Exception as e:
            logger.warning(f"before_tool_call hook error: {e}")


async def run_after_tool_call(
    name: str,
    arguments: dict[str, Any],
    result: str,
    error: str | None = None,
) -> None:
    for cb in _after_tool_call:
        try:
            await cb(name, arguments, result, error)
        except Exception as e:
            logger.warning(f"after_tool_call hook error: {e}")


async def run_after_response(
    session_id: str,
    content: str | None,
    tools_used: list[str],
) -> None:
    for cb in _after_response:
        try:
            await cb(session_id, content, tools_used)
        except Exception as e:
            logger.warning(f"after_response hook error: {e}")
