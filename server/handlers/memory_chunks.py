"""Long-term memory chunks HTTP handlers (Chroma)."""

from __future__ import annotations

from fastapi import HTTPException, Request

from server.long_term_memory import delete_chunks, get_chunk, list_chunks, update_chunk
from server.models import (
    MemoryChunkItem,
    MemoryChunksDeleteRequest,
    MemoryChunksListResponse,
    MemoryChunkUpdateRequest,
)


async def get_memory_chunks(
    request: Request,
    auth_user: object,
    limit: int = 50,
    offset: int = 0,
    run_id: str | None = None,
    date: str | None = None,
) -> MemoryChunksListResponse:
    """List long-term memory chunks with optional filters and pagination."""
    try:
        items, total = list_chunks(limit=limit, offset=offset, run_id=run_id, date=date)
        return MemoryChunksListResponse(
            chunks=[MemoryChunkItem(**x) for x in items],
            total=total,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


async def get_memory_chunk(
    chunk_id: str, request: Request, auth_user: object
) -> MemoryChunkItem:
    """Get a single long-term memory chunk by id."""
    try:
        item = get_chunk(chunk_id)
        if not item:
            raise HTTPException(status_code=404, detail="Chunk not found")
        return MemoryChunkItem(**item)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


async def patch_memory_chunk(
    chunk_id: str,
    request: Request,
    body: MemoryChunkUpdateRequest,
    auth_user: object,
) -> dict:
    """Update a chunk's document and re-embed."""
    try:
        ok = update_chunk(chunk_id, body.document)
        if not ok:
            raise HTTPException(status_code=404, detail="Chunk not found")
        return {"status": "updated"}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


async def delete_memory_chunks(
    request: Request, body: MemoryChunksDeleteRequest, auth_user: object
) -> dict:
    """Delete long-term memory chunks by id."""
    try:
        n = delete_chunks(body.ids)
        return {"status": "ok", "deleted": n}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
