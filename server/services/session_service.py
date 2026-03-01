"""
Session service: list, get, delete, rename, branch, retry, edit, set project.

Interface so handlers stay HTTP-only; implementation wraps nanobot SessionManager.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from server.models import MessageRecord, SessionDetail, SessionListItem

if TYPE_CHECKING:
    from nanobot.session.manager import SessionManager


class SessionService(Protocol):
    """Protocol for session operations used by handlers."""

    def list_sessions(self, q: str | None = None) -> list[SessionListItem]:
        ...

    def get_session(self, session_id: str) -> SessionDetail:
        ...

    def delete_session(self, session_id: str) -> None:
        ...

    def rename_session(self, session_id: str, title: str) -> None:
        ...

    def new_session(self, session_id: str) -> None:
        ...

    def set_project(self, session_id: str, project: str | None) -> str | None:
        ...

    def retry_session(
        self, session_id: str
    ) -> tuple[str, str, int]:
        """Returns (status, key, message_count)."""
        ...

    def branch_session(
        self, session_id: str, message_index: int
    ) -> tuple[str, str, int]:
        """Returns (status, new_key, message_count)."""
        ...

    def edit_session_message(
        self, session_id: str, message_index: int, new_content: str
    ) -> tuple[str, str, int]:
        """Returns (status, key, message_count)."""
        ...


class NanobotSessionService:
    """Implementation using nanobot SessionManager."""

    def __init__(self, session_manager: "SessionManager") -> None:
        self._sm = session_manager

    def list_sessions(self, q: str | None = None) -> list[SessionListItem]:
        raw = self._sm.list_sessions()
        items: list[SessionListItem] = []
        for entry in raw:
            key: str = entry.get("key", "")
            if ":" in key:
                channel, chat_id = key.split(":", 1)
            else:
                channel, chat_id = "unknown", key
            session = self._sm.get_or_create(key)
            msg_count = len(session.messages)
            title: str | None = session.metadata.get("title")
            if q and q.strip():
                ql = q.strip().lower()
                if ql not in (key or "").lower() and ql not in (chat_id or "").lower() and ql not in (title or "").lower():
                    continue
            items.append(SessionListItem(
                key=key,
                created_at=entry.get("created_at"),
                updated_at=entry.get("updated_at"),
                message_count=msg_count,
                channel=channel,
                chat_id=chat_id,
                title=title,
            ))
        return items

    def get_session(self, session_id: str) -> SessionDetail:
        session = self._sm.get_or_create(session_id)
        messages = []
        for m in session.messages:
            blocks = m.get("blocks")
            # Diagnostic: log when assistant messages have (or lack) blocks for tool-call visibility after reload
            if m.get("role") == "assistant":
                has_tool_call_blocks = (
                    blocks
                    and any(
                        (b if isinstance(b, dict) else {}).get("type") == "tool_call"
                        for b in (blocks or [])
                    )
                )
                logger.debug(
                    "get_session blocks for assistant message: has_blocks={} has_tool_call_blocks={}",
                    bool(blocks),
                    has_tool_call_blocks,
                )
            messages.append(
                MessageRecord(
                    role=m["role"],
                    content=m.get("content", ""),
                    timestamp=m.get("timestamp"),
                    tools_used=m.get("tools_used"),
                    blocks=blocks,
                )
            )
        return SessionDetail(
            key=session.key,
            created_at=session.created_at.isoformat() if session.created_at else None,
            updated_at=session.updated_at.isoformat() if session.updated_at else None,
            messages=messages,
            metadata=session.metadata,
        )

    def delete_session(self, session_id: str) -> None:
        self._sm.delete(session_id)

    def rename_session(self, session_id: str, title: str) -> None:
        session = self._sm.get_or_create(session_id)
        session.metadata["title"] = title
        self._sm.save(session)

    def new_session(self, session_id: str) -> None:
        session = self._sm.get_or_create(session_id)
        session.clear()
        self._sm.save(session)
        self._sm.invalidate(session_id)

    def set_project(self, session_id: str, project: str | None) -> str | None:
        session = self._sm.get_or_create(session_id)
        if project is None:
            session.metadata.pop("project", None)
        else:
            session.metadata["project"] = project.strip()
        self._sm.save(session)
        return session.metadata.get("project")

    def retry_session(self, session_id: str) -> tuple[str, str, int]:
        parent = self._sm.get_or_create(session_id)
        last_user_idx = -1
        for i in range(len(parent.messages) - 1, -1, -1):
            if parent.messages[i].get("role") == "user":
                last_user_idx = i
                break
        if last_user_idx < 0:
            return ("no_user_message", session_id, len(parent.messages))
        new_key = f"{session_id}:branch:{uuid.uuid4().hex[:12]}"
        branch = self._sm.get_or_create(new_key)
        for m in parent.messages[: last_user_idx + 1]:
            kwargs = {k: v for k, v in m.items() if k not in ("role", "content")}
            branch.add_message(m.get("role", "user"), m.get("content", ""), **kwargs)
        self._sm.save(branch)
        return ("branched", new_key, len(branch.messages))

    def branch_session(self, session_id: str, message_index: int) -> tuple[str, str, int]:
        parent = self._sm.get_or_create(session_id)
        if message_index < 0 or message_index >= len(parent.messages):
            raise ValueError("message_index out of range")
        new_key = f"web:{uuid.uuid4().hex}"
        branch = self._sm.get_or_create(new_key)
        branch.clear()
        branch.messages = [dict(m) for m in parent.messages[: message_index + 1]]
        branch.updated_at = datetime.now()
        self._sm.save(branch)
        return ("branched", new_key, len(branch.messages))

    def edit_session_message(
        self, session_id: str, message_index: int, new_content: str
    ) -> tuple[str, str, int]:
        session = self._sm.get_or_create(session_id)
        session.truncate_to(message_index)
        self._sm.save(session)
        return ("truncated", session_id, len(session.messages))
