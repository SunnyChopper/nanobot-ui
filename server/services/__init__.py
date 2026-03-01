"""
Service layer for the nanobot web server.

Handlers depend on service interfaces; implementations wrap existing
nanobot/server code so they can be swapped if needed.
"""

from server.services.session_service import SessionService, NanobotSessionService
from server.services.streaming import stream_agent_loop

__all__ = [
    "SessionService",
    "NanobotSessionService",
    "stream_agent_loop",
]
