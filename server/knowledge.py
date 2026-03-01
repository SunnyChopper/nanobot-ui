"""
Knowledge base API: KG triples (SQLite) and RAG chunks (Chroma at workspace/data/chroma).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from nanobot.config.loader import get_data_dir


# ---------------------------------------------------------------------------
# Knowledge graph (triples)
# ---------------------------------------------------------------------------


def _kg_path() -> Path:
    return get_data_dir() / "memory" / "knowledge_graph.db"


def list_triples(
    subject: str | None = None,
    predicate: str | None = None,
    object_: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    List triples with optional substring filters. Returns (list of {id, subject, predicate, object, created_at}, total).
    """
    path = _kg_path()
    if not path.exists():
        return ([], 0)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        where_parts: list[str] = []
        params: list[Any] = []
        if subject:
            where_parts.append("subject LIKE ?")
            params.append(f"%{subject}%")
        if predicate:
            where_parts.append("predicate LIKE ?")
            params.append(f"%{predicate}%")
        if object_:
            where_parts.append("object LIKE ?")
            params.append(f"%{object_}%")
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        count_sql = f"SELECT COUNT(*) FROM triples WHERE {where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]
        select_sql = f"SELECT id, subject, predicate, object, created_at FROM triples WHERE {where_sql} ORDER BY id LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(select_sql, params).fetchall()
        items = [
            {
                "id": row["id"],
                "subject": row["subject"],
                "predicate": row["predicate"],
                "object": row["object"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        return (items, total)
    finally:
        conn.close()


def get_triples_stats() -> dict[str, Any]:
    """Return total count and counts by predicate."""
    path = _kg_path()
    if not path.exists():
        return {"total": 0, "by_predicate": {}}
    conn = sqlite3.connect(str(path))
    try:
        total = conn.execute("SELECT COUNT(*) FROM triples").fetchone()[0]
        rows = conn.execute(
            "SELECT predicate, COUNT(*) AS c FROM triples GROUP BY predicate"
        ).fetchall()
        by_predicate = {row[0]: row[1] for row in rows}
        return {"total": total, "by_predicate": by_predicate}
    finally:
        conn.close()


def delete_triples(ids: list[int]) -> int:
    """Delete triples by primary key. Returns number deleted."""
    if not ids:
        return 0
    path = _kg_path()
    if not path.exists():
        return 0
    conn = sqlite3.connect(str(path))
    try:
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM triples WHERE id IN ({placeholders})", ids)
        conn.commit()
        return conn.total_changes
    finally:
        conn.close()


def add_triple(subject: str, predicate: str, object_: str) -> bool:
    """
    Insert a single triple into the KG. Returns True if inserted, False if duplicate.
    Ensures DB and triples table exist (same schema as memory_sleep).
    """
    path = _kg_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(subject, predicate, object)
            )"""
        )
        conn.commit()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        cursor = conn.execute(
            "INSERT OR IGNORE INTO triples (subject, predicate, object, created_at) VALUES (?, ?, ?, ?)",
            (subject.strip()[:500], predicate.strip()[:200], object_.strip()[:500], now),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# RAG (workspace/data/chroma, collection nanobot_rag)
# ---------------------------------------------------------------------------


def _rag_path(workspace_path: Path) -> Path:
    return workspace_path / "data" / "chroma"


def _ensure_rag_client(workspace_path: Path) -> tuple[Any, Any] | str:
    """Lazy-init RAG Chroma client and model. Returns (collection, model) or error string."""
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        return f"RAG requires chromadb and sentence-transformers: {e}"
    path = _rag_path(Path(workspace_path))
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(path),
        settings=Settings(anonymized_telemetry=False),
    )
    model = SentenceTransformer("all-MiniLM-L6-v2")
    coll = client.get_or_create_collection(
        name="nanobot_rag",
        metadata={"description": "Nanobot RAG documents"},
    )
    return (coll, model)


def list_rag_chunks(
    workspace_path: Path,
    limit: int = 50,
    offset: int = 0,
    source: str | None = None,
    q: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    List RAG chunks. If q is provided, semantic search is used. Optional source filter.
    Returns (list of {id, document, metadata}, total).
    """
    client_result = _ensure_rag_client(workspace_path)
    if isinstance(client_result, str):
        raise RuntimeError(client_result)
    coll, model = client_result
    if q and q.strip():
        # Semantic search: query and return matching chunks
        emb = model.encode([q.strip()]).tolist()
        kwargs: dict[str, Any] = {
            "query_embeddings": emb,
            "n_results": min(limit, 100),
            "include": ["documents", "metadatas"],
        }
        if source:
            kwargs["where"] = {"source": source}
        result = coll.query(**kwargs)
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        total = len(ids)
        items = [
            {
                "id": ids[i],
                "document": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
            }
            for i in range(len(ids))
        ]
        return (items, total)
    # List with optional source filter
    where = {"source": source} if source else None
    if where:
        count_result = coll.get(where=where, include=[])
        total = len(count_result.get("ids") or [])
    else:
        total = coll.count()
    kwargs = {
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


def get_rag_sources(workspace_path: Path) -> list[str]:
    """Return distinct metadata.source values from RAG collection."""
    client_result = _ensure_rag_client(workspace_path)
    if isinstance(client_result, str):
        raise RuntimeError(client_result)
    coll, _ = client_result
    result = coll.get(include=["metadatas"])
    metadatas = result.get("metadatas") or []
    sources: set[str] = set()
    for m in metadatas:
        if isinstance(m, dict) and "source" in m:
            sources.add(str(m["source"]))
    return sorted(sources)


def delete_rag_chunks(workspace_path: Path, ids: list[str]) -> int:
    """Delete RAG chunks by id. Returns number deleted."""
    if not ids:
        return 0
    client_result = _ensure_rag_client(workspace_path)
    if isinstance(client_result, str):
        raise RuntimeError(client_result)
    coll, _ = client_result
    coll.delete(ids=ids)
    return len(ids)
