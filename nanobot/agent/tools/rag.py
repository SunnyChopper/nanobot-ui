"""
Local RAG (Retrieval-Augmented Generation) tool.

Semantic search over ingested documents using ChromaDB and sentence-transformers.
Use rag_ingest to add files to the index, then semantic_search to query.
"""

import hashlib
import uuid
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool

# Module-level lazy state shared by both tools
_rag_collection = None
_rag_model = None
_rag_client = None


def _ensure_rag(persist_directory: Path | None = None) -> tuple[Any, Any] | str:
    """Lazy-init ChromaDB and embedding model. Returns (collection, model) or error string."""
    global _rag_collection, _rag_model, _rag_client
    if _rag_collection is not None and _rag_model is not None:
        return (_rag_collection, _rag_model)
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        return f"RAG not available: install chromadb and sentence-transformers. Error: {e}"
    persist = persist_directory or Path.home() / ".nanobot" / "chroma"
    persist.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(persist),
        settings=Settings(anonymized_telemetry=False),
    )
    _rag_client = client
    _rag_model = SentenceTransformer("all-MiniLM-L6-v2")
    _rag_collection = client.get_or_create_collection(
        name="nanobot_rag",
        metadata={"description": "Nanobot RAG documents"},
    )
    return (_rag_collection, _rag_model)


class SemanticSearchTool(Tool):
    """Tool to semantically search previously ingested documents (PDFs, code, markdown)."""

    def __init__(self, persist_directory: Path | None = None):
        self._persist_directory = persist_directory

    def _ensure_ready(self) -> str | None:
        r = _ensure_rag(self._persist_directory)
        return r if isinstance(r, str) else None

    @property
    def name(self) -> str:
        return "semantic_search"

    @property
    def description(self) -> str:
        return (
            "Semantically search documents that have been ingested into the local RAG index "
            "(PDFs, code, markdown). Returns the most relevant text chunks. Use when you need "
            "to find information from the user's indexed documents."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of chunks to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, top_k: int = 5, **kwargs: Any) -> str:
        err = self._ensure_ready()
        if err:
            return err
        coll, model = _ensure_rag(self._persist_directory)
        top_k = max(1, min(top_k, 20))
        try:
            query_embedding = model.encode([query]).tolist()
            results = coll.query(
                query_embeddings=query_embedding,
                n_results=top_k,
                include=["documents", "metadatas"],
            )
            docs = results.get("documents", [[]])
            metadatas = results.get("metadatas", [[]])
            if not docs or not docs[0]:
                return "No documents found in the RAG index. Use rag_ingest to add files first."
            lines = []
            for i, (doc, meta) in enumerate(zip(docs[0], metadatas[0] or []), 1):
                source = (meta or {}).get("source", "?")
                lines.append(f"[{i}] (from {source})\n{doc}")
            return "\n\n---\n\n".join(lines)
        except Exception as e:
            return f"Search error: {e}"


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    return chunks


class RagIngestTool(Tool):
    """Tool to ingest a text file into the RAG index for semantic search."""

    def __init__(self, persist_directory: Path | None = None, allowed_dir: Path | None = None):
        self._persist_directory = persist_directory
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "rag_ingest"

    @property
    def description(self) -> str:
        return (
            "Ingest a text or markdown file into the local RAG index so that semantic_search "
            "can find relevant passages. Use for .txt, .md, or other text files."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to ingest (text or markdown)",
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        r = _ensure_rag(self._persist_directory)
        if isinstance(r, str):
            return r
        coll, model = r
        try:
            p = Path(path).expanduser().resolve()
            if self._allowed_dir and not str(p).startswith(str(self._allowed_dir.resolve())):
                return f"Error: path is outside allowed directory {self._allowed_dir}"
            if not p.exists() or not p.is_file():
                return f"Error: file not found: {path}"
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading file: {e}"
        if not content.strip():
            return "File is empty."
        chunks = _chunk_text(content)
        if not chunks:
            return "No chunks extracted."
        source = str(p)
        doc_ids = [f"{hashlib.md5((source + str(i)).encode()).hexdigest()}_{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
        embeddings = model.encode(chunks).tolist()
        metadatas = [{"source": source} for _ in chunks]
        try:
            coll.add(ids=doc_ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
        except Exception as e:
            return f"Ingest error: {e}"
        return f"Ingested {len(chunks)} chunks from {source}."
