"""
Memory sleep pipeline: scheduled consolidation of MEMORY.md and HISTORY.md
into a vector DB (long-term memory) and a knowledge graph (derived insights).

Runs as a cron job with kind="memory_sleep". Does not run an agent turn.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import json_repair
from litellm import acompletion
from loguru import logger

from nanobot.agent.memory import MemoryStore
from nanobot.config.loader import get_data_dir
from nanobot.providers.litellm_provider import resolve_model

if TYPE_CHECKING:
    from nanobot.config.schema import Config

# Default limits for synthesis input (avoid huge prompts)
MAX_MEMORY_CHARS = 30_000
MAX_HISTORY_CHARS = 50_000
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DEFAULT_ARCHIVE_THRESHOLD_BYTES = 200_000  # ~200KB before archiving


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
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


def _sleep_state_path(workspace_path: Path) -> Path:
    """Path to the sleep state file (per-workspace)."""
    return workspace_path / "memory" / ".sleep_state.json"


def _load_state(workspace_path: Path) -> dict[str, Any]:
    """Load last run state."""
    path = _sleep_state_path(workspace_path)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Memory sleep: could not load state: {e}")
    return {}


def _save_state(workspace_path: Path, state: dict[str, Any]) -> None:
    """Persist state after successful run."""
    path = _sleep_state_path(workspace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _ensure_long_term_chroma(persist_path: Path) -> tuple[Any, Any] | str:
    """Lazy-init Chroma client and collection for long-term memory (separate from RAG)."""
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        return f"Memory sleep (vector): chromadb or sentence-transformers not installed: {e}"
    persist_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(persist_path),
        settings=Settings(anonymized_telemetry=False),
    )
    model = SentenceTransformer("all-MiniLM-L6-v2")
    coll = client.get_or_create_collection(
        name="long_term_memory",
        metadata={"description": "Long-term memory from MEMORY.md and HISTORY.md consolidation"},
    )
    return (coll, model)


def _ensure_kg(db_path: Path) -> str | None:
    """Ensure SQLite KG exists with triples table. Returns None on success, error string otherwise."""
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
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
        conn.close()
        return None
    except Exception as e:
        return str(e)


def _insert_triples(db_path: Path, triples: list[tuple[str, str, str]]) -> int:
    """Insert triples into KG, ignoring duplicates. Returns number inserted."""
    if not triples:
        return 0
    now = datetime.utcnow().isoformat() + "Z"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    inserted = 0
    for s, p, o in triples:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO triples (subject, predicate, object, created_at) VALUES (?, ?, ?, ?)",
                (s.strip()[:500], p.strip()[:200], o.strip()[:500], now),
            )
            if cursor.rowcount:
                inserted += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return inserted


async def _call_llm(
    config: "Config",
    prompt: str,
    system: str,
    model_key: str = "memory_model",
) -> str | None:
    """Call LLM for synthesis or KG extraction. Returns response text or None on failure."""
    model = (getattr(config.agents.defaults, model_key, None) or config.agents.defaults.model or "").strip()
    if not model:
        logger.warning("Memory sleep: no model configured")
        return None
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)
    api_key = p.api_key if p else None
    api_base = config.get_api_base(model)
    extra_headers = p.extra_headers if p else None
    resolved = resolve_model(model, provider_name=provider_name, api_key=api_key, api_base=api_base)
    kwargs: dict[str, Any] = {
        "model": resolved,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
        "temperature": 0.3,
        "stream": False,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
    if extra_headers:
        kwargs["extra_headers"] = extra_headers
    try:
        response = await acompletion(**kwargs)
        if response.choices and response.choices[0].message and response.choices[0].message.content:
            return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"Memory sleep LLM call failed: {e}")
    return None


async def run_memory_sleep(workspace_path: Path, config: "Config") -> str | None:
    """
    Run the memory sleep pipeline: read MEMORY.md and HISTORY.md, synthesize,
    push to vector DB and knowledge graph, optionally archive. Returns a short
    status string or None on failure. Updates state only on full success.
    """
    workspace_path = Path(workspace_path).resolve()
    memory = MemoryStore(workspace_path)
    state = _load_state(workspace_path)
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    try:
        # 1. Read inputs (bounded)
        memory_content = memory.read_long_term() or ""
        history_content = memory.read_history() or ""
        if len(memory_content) > MAX_MEMORY_CHARS:
            memory_content = memory_content[-MAX_MEMORY_CHARS:]
        if len(history_content) > MAX_HISTORY_CHARS:
            history_content = history_content[-MAX_HISTORY_CHARS:]

        combined = f"## Long-term memory\n{memory_content}\n\n## History log\n{history_content}"
        if not combined.strip():
            logger.info("Memory sleep: no memory or history content, skipping")
            return "ok (no content)"

        # 2. Optional synthesis
        synthesis_prompt = f"""Summarize the following memory and history into a concise consolidation (key facts, decisions, events, and context). Keep it under 2000 words. Do not include raw timestamps or log noise; extract the substance.

{combined}"""
        synthesized = await _call_llm(
            config,
            synthesis_prompt,
            system="You are a memory consolidation agent. Output a clear, structured summary.",
        )
        if not synthesized:
            synthesized = combined

        # 3. Vector DB: chunk, embed, store
        data_dir = get_data_dir()
        chroma_path = data_dir / "memory" / "chroma"
        chroma_result = _ensure_long_term_chroma(chroma_path)
        if isinstance(chroma_result, str):
            logger.warning(f"Memory sleep: {chroma_result}")
        else:
            coll, model = chroma_result
            chunks = _chunk_text(synthesized)
            if chunks:
                doc_ids = [f"sleep_{run_id}_{i}_{hashlib.md5(chunks[i].encode()).hexdigest()[:8]}" for i in range(len(chunks))]
                embeddings = model.encode(chunks).tolist()
                metadatas = [{"source": "memory_sleep", "date": run_id, "run_id": run_id} for _ in chunks]
                try:
                    coll.add(ids=doc_ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
                    logger.info(f"Memory sleep: ingested {len(chunks)} chunks into long_term_memory")
                except Exception as e:
                    logger.warning(f"Memory sleep: Chroma add failed: {e}")

        # 4. Knowledge graph: extract triples from synthesized text
        kg_path = data_dir / "memory" / "knowledge_graph.db"
        err = _ensure_kg(kg_path)
        if err:
            logger.warning(f"Memory sleep: KG init failed: {err}")
        else:
            kg_prompt = f"""From the following text, extract factual knowledge as subject-predicate-object triples. Output ONLY a JSON array of objects with keys "subject", "predicate", "object". Use short, normalized phrases. Example: [{{"subject": "User", "predicate": "prefers", "object": "dark mode"}}]. Extract at most 30 triples.

Text:
{synthesized[:6000]}"""
            kg_text = await _call_llm(
                config,
                kg_prompt,
                system="You output only valid JSON arrays. No markdown, no explanation.",
            )
            if kg_text:
                if kg_text.startswith("```"):
                    kg_text = kg_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                try:
                    arr = json_repair.loads(kg_text)
                    if isinstance(arr, list):
                        triples = []
                        for item in arr:
                            if isinstance(item, dict) and "subject" in item and "predicate" in item and "object" in item:
                                triples.append((str(item["subject"]), str(item["predicate"]), str(item["object"])))
                        inserted = _insert_triples(kg_path, triples)
                        logger.info(f"Memory sleep: inserted {inserted} triples into knowledge graph")
                except Exception as e:
                    logger.warning(f"Memory sleep: KG parse/insert failed: {e}")

        # 5. Optional archiving: if HISTORY.md is large, archive and start fresh
        archive_threshold = getattr(
            getattr(config, "memory_sleep", None),
            "archive_threshold_bytes",
            DEFAULT_ARCHIVE_THRESHOLD_BYTES,
        )
        history_file = memory.history_file
        if history_file.exists() and archive_threshold > 0:
            size = history_file.stat().st_size
            if size >= archive_threshold:
                archive_name = f"HISTORY_archive_{datetime.utcnow().strftime('%Y-%m-%d')}.md"
                archive_path = memory.memory_dir / archive_name
                try:
                    content = history_file.read_text(encoding="utf-8")
                    archive_path.write_text(content, encoding="utf-8")
                    history_file.write_text("", encoding="utf-8")
                    logger.info(f"Memory sleep: archived HISTORY.md to {archive_name}")
                except Exception as e:
                    logger.warning(f"Memory sleep: archive failed: {e}")

        # 6. Update state only on success
        state["last_run_at"] = datetime.utcnow().isoformat() + "Z"
        state["last_run_id"] = run_id
        _save_state(workspace_path, state)
        return "ok"
    except Exception as e:
        logger.error(f"Memory sleep failed: {e}")
        return None
