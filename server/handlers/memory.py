"""Memory HTTP handlers: MEMORY.md / HISTORY.md read/write and tasks."""

from __future__ import annotations

from fastapi import Request

from server.models import (
    MemoryHistoryAppendRequest,
    MemoryHistoryPut,
    MemoryHistoryRemoveEntriesRequest,
    MemoryLongTermPut,
    MemoryResponse,
    ScanIrrelevantHistoryResponse,
    VerifyBulletRequest,
    VerifyBulletResponse,
)


async def get_memory(request: Request, auth_user: object) -> MemoryResponse:
    """Read MEMORY.md and HISTORY.md from the workspace memory directory."""
    from nanobot.agent.memory import MemoryStore

    config = request.app.state.config
    store = MemoryStore(config.workspace_path)
    return MemoryResponse(
        memory=store.read_long_term(),
        history=store.read_history(),
    )


async def put_memory_long_term(
    request: Request, body: MemoryLongTermPut, auth_user: object
) -> dict:
    """Overwrite MEMORY.md with the given content."""
    from nanobot.agent.memory import MemoryStore

    config = request.app.state.config
    store = MemoryStore(config.workspace_path)
    store.write_long_term(body.content)
    return {"status": "saved"}


async def put_memory_history(
    request: Request, body: MemoryHistoryPut, auth_user: object
) -> dict:
    """Overwrite HISTORY.md with the given content."""
    from nanobot.agent.memory import MemoryStore

    config = request.app.state.config
    store = MemoryStore(config.workspace_path)
    store.history_file.write_text(body.content, encoding="utf-8")
    return {"status": "saved"}


async def post_memory_history_append(
    request: Request, body: MemoryHistoryAppendRequest, auth_user: object
) -> dict:
    """Append one entry to HISTORY.md."""
    from nanobot.agent.memory import MemoryStore

    config = request.app.state.config
    store = MemoryStore(config.workspace_path)
    store.append_history(body.entry)
    return {"status": "appended"}


async def post_memory_tasks_verify_bullet(
    request: Request, body: VerifyBulletRequest, auth_user: object
) -> VerifyBulletResponse:
    """Ask LLM whether the given bullet/fact is still accurate."""
    from server.memory_tasks import run_verify_bullet

    config = request.app.state.config
    result = await run_verify_bullet(config.workspace_path, config, body.text)
    return VerifyBulletResponse(verified=result["verified"], comment=result["comment"])


async def post_memory_tasks_scan_irrelevant_history(
    request: Request, auth_user: object
) -> ScanIrrelevantHistoryResponse:
    """Ask LLM to identify HISTORY.md entries that seem irrelevant."""
    from server.memory_tasks import run_scan_irrelevant_history

    config = request.app.state.config
    result = await run_scan_irrelevant_history(config.workspace_path, config)
    return ScanIrrelevantHistoryResponse(irrelevant_indices=result["irrelevant_indices"])


async def post_memory_history_remove_entries(
    request: Request, body: MemoryHistoryRemoveEntriesRequest, auth_user: object
) -> dict:
    """Remove HISTORY.md entries by 0-based index."""
    from server.memory_tasks import remove_history_entries

    config = request.app.state.config
    removed = remove_history_entries(config.workspace_path, body.indices)
    return {"status": "ok", "removed": removed}
