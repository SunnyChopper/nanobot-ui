"""Knowledge base HTTP handlers: KG triples and RAG chunks."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request

from server.knowledge import (
    delete_rag_chunks,
    delete_triples,
    get_rag_sources,
    get_triples_stats,
    list_rag_chunks,
    list_triples,
)
from server.models import (
    RagChunkItem,
    RagChunksDeleteRequest,
    RagChunksListResponse,
    RagSourcesResponse,
    TripleItem,
    TriplesDeleteRequest,
    TriplesListResponse,
    TriplesStatsResponse,
)


async def get_knowledge_triples(
    auth_user: object,
    subject: str | None = None,
    predicate: str | None = None,
    object_: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> TriplesListResponse:
    """List knowledge graph triples with optional substring filters."""
    items, total = list_triples(
        subject=subject,
        predicate=predicate,
        object_=object_,
        limit=limit,
        offset=offset,
    )
    return TriplesListResponse(
        triples=[
            TripleItem(
                id=x["id"],
                subject=x["subject"],
                predicate=x["predicate"],
                object=x["object"],
                created_at=x.get("created_at") or "",
            )
            for x in items
        ],
        total=total,
    )


async def get_knowledge_triples_stats(auth_user: object) -> TriplesStatsResponse:
    """Return total triple count and counts by predicate."""
    stats = get_triples_stats()
    return TriplesStatsResponse(
        total=stats["total"],
        by_predicate=stats.get("by_predicate") or {},
    )


async def delete_knowledge_triples(
    request: Request, body: TriplesDeleteRequest, auth_user: object
) -> dict:
    """Delete triples by primary key."""
    n = delete_triples(body.ids)
    return {"status": "ok", "deleted": n}


async def get_knowledge_rag_chunks(
    request: Request,
    auth_user: object,
    limit: int = 50,
    offset: int = 0,
    source: str | None = None,
    q: str | None = None,
) -> RagChunksListResponse:
    """List RAG chunks. Use q for semantic search. Optional source filter."""
    config = request.app.state.config
    try:
        items, total = list_rag_chunks(
            Path(config.workspace_path),
            limit=limit,
            offset=offset,
            source=source,
            q=q,
        )
        return RagChunksListResponse(
            chunks=[RagChunkItem(**x) for x in items],
            total=total,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


async def get_knowledge_rag_sources(
    request: Request, auth_user: object
) -> RagSourcesResponse:
    """List distinct RAG source paths."""
    config = request.app.state.config
    try:
        sources = get_rag_sources(Path(config.workspace_path))
        return RagSourcesResponse(sources=sources)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


async def delete_knowledge_rag_chunks(
    request: Request, body: RagChunksDeleteRequest, auth_user: object
) -> dict:
    """Delete RAG chunks by id."""
    config = request.app.state.config
    try:
        n = delete_rag_chunks(Path(config.workspace_path), body.ids)
        return {"status": "ok", "deleted": n}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
