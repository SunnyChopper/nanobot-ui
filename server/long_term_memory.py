"""
Long-term memory chunks API: list, get, update, delete for Chroma collection long_term_memory.
Uses same path and embedding model as memory_sleep for consistency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nanobot.config.loader import get_data_dir


def _chroma_path() -> Path:
    return get_data_dir() / "memory" / "chroma"


def _ensure_client():
    """Lazy-init Chroma client, collection, and embedding model. Returns (coll, model) or raises."""
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError(
            "Long-term memory requires chromadb and sentence-transformers"
        ) from e
    path = _chroma_path()
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(path),
        settings=Settings(anonymized_telemetry=False),
    )
    model = SentenceTransformer("all-MiniLM-L6-v2")
    coll = client.get_or_create_collection(
        name="long_term_memory",
        metadata={"description": "Long-term memory from MEMORY.md and HISTORY.md consolidation"},
    )
    return (coll, model)


def list_chunks(
    limit: int = 50,
    offset: int = 0,
    run_id: str | None = None,
    date: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    List chunks with optional metadata filters. Returns (list of {id, document, metadata}, total).
    """
    coll, _ = _ensure_client()
    where: dict[str, Any] = {}
    if run_id is not None:
        where["run_id"] = run_id
    if date is not None:
        where["date"] = date
    if where:
        # Get total count for filtered query
        count_result = coll.get(where=where, include=[])
        total = len(count_result.get("ids") or [])
    else:
        total = coll.count()
    kwargs: dict[str, Any] = {
        "include": ["documents", "metadatas"],
        "limit": min(limit, 200),
        "offset": offset,
    }
    if where:
        kwargs["where"] = where
    result = coll.get(**kwargs)
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    items = [
        {
            "id": ids[i],
            "document": documents[i] if i < len(documents) else "",
            "metadata": metadatas[i] if i < len(metadatas) else {},
        }
        for i in range(len(ids))
    ]
    return (items, total)


def get_chunk(chunk_id: str) -> dict[str, Any] | None:
    """Get a single chunk by id. Returns {id, document, metadata} or None."""
    coll, _ = _ensure_client()
    result = coll.get(ids=[chunk_id], include=["documents", "metadatas"])
    ids = result.get("ids") or []
    if not ids:
        return None
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    return {
        "id": ids[0],
        "document": documents[0] if documents else "",
        "metadata": metadatas[0] if metadatas else {},
    }


def update_chunk(chunk_id: str, document: str) -> bool:
    """Update chunk document and re-embed. Returns True if updated."""
    coll, model = _ensure_client()
    existing = coll.get(ids=[chunk_id], include=["documents"])
    if not (existing.get("ids")):
        return False
    embedding = model.encode([document]).tolist()
    coll.update(ids=[chunk_id], documents=[document], embeddings=embedding)
    return True


def delete_chunks(ids: list[str]) -> int:
    """Delete chunks by id. Returns number deleted."""
    if not ids:
        return 0
    coll, _ = _ensure_client()
    coll.delete(ids=ids)
    return len(ids)
