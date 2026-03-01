"""
Session and projects HTTP handlers.

Delegates to SessionService; list_projects uses config + server.projects.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from server.models import (
    BranchSessionRequest,
    EditMessageRequest,
    RenameSessionRequest,
    SessionDetail,
    SessionListItem,
    SessionProjectPatch,
)


async def list_sessions(
    request: Request,
    auth_user: object,
    q: str | None = None,
) -> list[SessionListItem]:
    """List all chat sessions with optional search filter."""
    svc = request.app.state.session_service
    return svc.list_sessions(q=q)


async def get_session(
    session_id: str,
    request: Request,
    auth_user: object,
) -> SessionDetail:
    """Get full session history."""
    svc = request.app.state.session_service
    return svc.get_session(session_id)


async def delete_session(
    session_id: str,
    request: Request,
    auth_user: object,
) -> dict:
    """Permanently delete a session."""
    svc = request.app.state.session_service
    svc.delete_session(session_id)
    return {"status": "deleted", "key": session_id}


async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    request: Request,
    auth_user: object,
) -> dict:
    """Rename a session by setting title in metadata."""
    svc = request.app.state.session_service
    svc.rename_session(session_id, body.title)
    return {"status": "renamed", "key": session_id, "title": body.title}


async def new_session(
    session_id: str,
    request: Request,
    auth_user: object,
) -> dict:
    """Start a new conversation (clear history)."""
    svc = request.app.state.session_service
    svc.new_session(session_id)
    return {"status": "new_session", "key": session_id}


async def set_session_project(
    session_id: str,
    body: SessionProjectPatch,
    request: Request,
    auth_user: object,
) -> dict:
    """Set or clear the active project for this session."""
    svc = request.app.state.session_service
    project = svc.set_project(session_id, body.project)
    return {"status": "ok", "key": session_id, "project": project}


async def retry_session(
    session_id: str,
    request: Request,
    auth_user: object,
) -> dict:
    """Branch from last user message and return new key / message count."""
    svc = request.app.state.session_service
    status, key, message_count = svc.retry_session(session_id)
    return {"status": status, "key": key, "message_count": message_count}


async def branch_session(
    session_id: str,
    body: BranchSessionRequest,
    request: Request,
    auth_user: object,
) -> dict:
    """Branch from a specific message into a new session."""
    svc = request.app.state.session_service
    try:
        status, new_key, message_count = svc.branch_session(session_id, body.message_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": status, "key": new_key, "message_count": message_count}


async def edit_session_message(
    session_id: str,
    body: EditMessageRequest,
    request: Request,
    auth_user: object,
) -> dict:
    """Truncate session to message_index (exclusive); frontend sends new_content as new message."""
    svc = request.app.state.session_service
    status, key, message_count = svc.edit_session_message(
        session_id, body.message_index, body.new_content
    )
    return {"status": status, "key": key, "message_count": message_count}


async def list_projects(request: Request) -> list[dict]:
    """List projects from ~/.nanobot/projects.json for Project Context Switcher."""
    from server.projects import load_projects

    config = request.app.state.config
    projects = load_projects(config.workspace_path)
    return [{"name": k, "path": v} for k, v in sorted(projects.items())]
