"""
Server-side channel adapters for the nanobot message bus.

WebChannel delivers outbound messages (e.g. subagent callbacks) to the
WebSocket connection registry so the frontend receives them in real time.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from nanobot.bus.events import OutboundMessage


class WebChannel:
    """
    Duck-typed channel that delivers OutboundMessage to WebSocket clients.
    Used for async callbacks (e.g. subagent done) to the web UI.
    """

    def __init__(self, registry: Any) -> None:
        """
        Args:
            registry: ConnectionRegistry from server.websocket (get(session_id) -> WebSocket | None).
        """
        self._registry = registry
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """No-op; web connections are managed by the WebSocket endpoint."""
        self._running = True

    async def stop(self) -> None:
        """No-op."""
        self._running = False

    async def send(self, msg: "OutboundMessage") -> None:
        """
        Send the message to the WebSocket client for msg.chat_id (session id).
        Sends a single frame: {"type": "assistant_message", "session_id": "...", "content": "..."}.
        """
        session_id = msg.chat_id
        ws = self._registry.get(session_id)
        if ws is None:
            logger.debug(f"WebChannel: no connection for session_id={session_id}, skipping outbound")
            return
        frame = {
            "type": "assistant_message",
            "session_id": session_id,
            "content": msg.content or "",
        }
        try:
            await ws.send_text(json.dumps(frame))
        except Exception as e:
            logger.warning(f"WebChannel: failed to send to {session_id}: {e}")
