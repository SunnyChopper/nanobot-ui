"""
Personal OS API tools: send message and create task.

Configure via env: PERSONAL_OS_BASE_URL (required), optional PERSONAL_OS_API_KEY.
Credentials should be resolved at runtime (e.g. Bitwarden); do not hardcode.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from nanobot.agent.tools.base import Tool


def _base_url() -> str | None:
    return os.environ.get("PERSONAL_OS_BASE_URL", "").rstrip("/") or None


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    key = os.environ.get("PERSONAL_OS_API_KEY")
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


class PersonalOsSendMessageTool(Tool):
    """Send a message to the user in the Personal OS web client."""

    @property
    def name(self) -> str:
        return "personal_os_send_message"

    @property
    def description(self) -> str:
        return "Send a message to the user in the Personal OS client. Requires PERSONAL_OS_BASE_URL."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Message content (markdown supported)"},
                "title": {"type": "string", "description": "Optional title"},
            },
            "required": ["content"],
        }

    async def execute(self, content: str, title: str = "", **kwargs: Any) -> str:
        base = _base_url()
        if not base:
            return "PERSONAL_OS_BASE_URL is not set. Cannot send message."
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{base}/api/messages",
                    json={"content": content, "title": title or None},
                    headers=_headers(),
                )
                if r.is_success:
                    return "Message sent."
                return f"Personal OS API error: {r.status_code} {r.text}"
        except Exception as e:
            return f"Failed to send message: {e}"


class PersonalOsCreateTaskTool(Tool):
    """Create a task in Personal OS."""

    @property
    def name(self) -> str:
        return "personal_os_create_task"

    @property
    def description(self) -> str:
        return "Create a task in the Personal OS client. Requires PERSONAL_OS_BASE_URL."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "body": {"type": "string", "description": "Optional task body/description"},
            },
            "required": ["title"],
        }

    async def execute(self, title: str, body: str = "", **kwargs: Any) -> str:
        base = _base_url()
        if not base:
            return "PERSONAL_OS_BASE_URL is not set. Cannot create task."
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{base}/api/tasks",
                    json={"title": title, "body": body or None},
                    headers=_headers(),
                )
                if r.is_success:
                    return "Task created."
                return f"Personal OS API error: {r.status_code} {r.text}"
        except Exception as e:
            return f"Failed to create task: {e}"


def create_personal_os_tools() -> list[Tool]:
    """Create Personal OS tools if base URL is set."""
    if not _base_url():
        return []
    return [PersonalOsSendMessageTool(), PersonalOsCreateTaskTool()]
