"""
Knowledge graph deduplication: merge semantically similar nodes and remove
duplicate triples. Runs synchronously (for asyncio.to_thread) with optional
progress callback and audit log.

Uses local SentenceTransformer for embeddings; no API cost.
Embeddings are cached in the KG DB and reused across runs (only new content is embedded).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import struct
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

from server.kg_dedup_llm import (
    LlmDedupGroup,
    apply_decisions_to_batch,
    ask_llm_merge_decisions,
    format_triple_phrase,
    reindex_batch,
)

if TYPE_CHECKING:
    from nanobot.config.schema import Config


@dataclass
class Phase1Result:
    """Result of load + exact dedup + embed + top-3: triples to work on and groups for the LLM."""

    kept: list[tuple[str, str, str]]
    groups: list[LlmDedupGroup]
    triples_before: int
    nodes_before: int

# Embedding cache table in same DB as triples. Key = content_hash (sha256 of model_name + content).
_EMBEDDING_CACHE_TABLE = "embedding_cache"
_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# Progress callback: (phase, current, total, message) -> None. Thread-safe if it only enqueues.
ProgressCallback = Callable[[str, int, int, str], None]


def _normalize_node(text: str) -> str:
    """Normalize a node label for consistent comparison."""
    if not text:
        return ""
    return " ".join(text.strip().split())[:500]


def _load_triples(kg_path: Path) -> list[tuple[int, str, str, str]]:
    """Load all triples (id, subject, predicate, object). Returns empty list if DB missing."""
    if not kg_path.exists():
        return []
    conn = sqlite3.connect(str(kg_path))
    try:
        rows = conn.execute(
            "SELECT id, subject, predicate, object FROM triples"
        ).fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]
    finally:
        conn.close()


def _content_hash(model_name: str, content: str) -> str:
    """Stable hash for cache key (model + content)."""
    return hashlib.sha256((model_name + "\0" + content).encode("utf-8")).hexdigest()


def _ensure_embedding_cache(conn: sqlite3.Connection) -> None:
    """Create embedding_cache table if missing."""
    conn.execute(
        f"""CREATE TABLE IF NOT EXISTS {_EMBEDDING_CACHE_TABLE} (
            content_hash TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            embedding_blob BLOB NOT NULL
        )"""
    )


def _decode_embedding(blob: bytes) -> list[float]:
    """Decode embedding stored as little-endian float32."""
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


def _encode_embedding(vec: list[float]) -> bytes:
    """Encode embedding as little-endian float32."""
    return struct.pack(f"<{len(vec)}f", *vec)


def _get_cached_embeddings(
    conn: sqlite3.Connection, model_name: str, texts: list[str]
) -> dict[str, list[float]]:
    """Return map of text -> embedding for texts that are in cache."""
    out: dict[str, list[float]] = {}
    if not texts:
        return out
    placeholders = ",".join("?" * len(texts))
    hashes = [_content_hash(model_name, t) for t in texts]
    rows = conn.execute(
        f"SELECT content_hash, embedding_blob FROM {_EMBEDDING_CACHE_TABLE} WHERE content_hash IN ({placeholders})",
        hashes,
    ).fetchall()
    hash_to_blob = {r[0]: r[1] for r in rows}
    for t in texts:
        h = _content_hash(model_name, t)
        if h in hash_to_blob:
            out[t] = _decode_embedding(hash_to_blob[h])
    return out


def _store_embeddings(
    conn: sqlite3.Connection, model_name: str, text_to_embedding: dict[str, list[float]]
) -> None:
    """Insert or replace embeddings in cache."""
    if not text_to_embedding:
        return
    rows = [
        (_content_hash(model_name, t), model_name, _encode_embedding(emb))
        for t, emb in text_to_embedding.items()
    ]
    conn.executemany(
        f"""INSERT OR REPLACE INTO {_EMBEDDING_CACHE_TABLE} (content_hash, model_name, embedding_blob) VALUES (?, ?, ?)""",
        rows,
    )
    conn.commit()


def _embed_texts_with_cache(
    kg_path: Path,
    model: Any,
    model_name: str,
    texts: list[str],
    *,
    batch_size: int = 256,
    progress_callback: ProgressCallback | None = None,
    progress_phase: str = "embed",
    progress_message: str = "Embedding…",
) -> list[list[float]]:
    """
    Return embeddings for `texts` in the same order. Uses DB cache at kg_path;
    only encodes texts not in cache and stores them. Requires sentence_transformers model.
    """
    if not texts:
        return []
    conn = sqlite3.connect(str(kg_path))
    try:
        _ensure_embedding_cache(conn)
        cached = _get_cached_embeddings(conn, model_name, texts)
        uncached = [t for t in texts if t not in cached]
        if uncached:
            num_batches = max(1, (len(uncached) + batch_size - 1) // batch_size)
            for b in range(num_batches):
                start_i = b * batch_size
                end_i = min(start_i + batch_size, len(uncached))
                batch = uncached[start_i:end_i]
                emb_list = model.encode(batch, show_progress_bar=False).tolist()
                to_store = dict(zip(batch, emb_list))
                _store_embeddings(conn, model_name, to_store)
                for t, emb in to_store.items():
                    cached[t] = emb
                if progress_callback:
                    progress_callback(
                        progress_phase,
                        b + 1,
                        num_batches,
                        f"{progress_message} (batch {b + 1}/{num_batches})…",
                    )
        elif progress_callback:
            progress_callback(progress_phase, 1, 1, "Using cached embeddings")
        return [cached[t] for t in texts]
    finally:
        conn.close()


def _run_phase1_sync(
    kg_path: Path,
    *,
    batch_size: int = 256,
    progress_callback: ProgressCallback | None = None,
) -> Phase1Result:
    """
    Load triples, exact (s,p,o) dedup, embed phrases, compute top-3 per triple.
    Returns a Phase1Result with kept triples, groups for the LLM, and counts.
    """
    import numpy as np

    progress = progress_callback or (lambda *a: None)

    progress("load", 0, 1, "Loading triples…")
    triples = _load_triples(kg_path)
    n_raw = len(triples)
    if n_raw == 0:
        return Phase1Result(kept=[], groups=[], triples_before=0, nodes_before=0)

    # Exact dedup: unique by normalized (s, p, o)
    seen: set[tuple[str, str, str]] = set()
    kept: list[tuple[str, str, str]] = []
    for _id, s, p, o in triples:
        t = (_normalize_node(s), _normalize_node(p), _normalize_node(o))
        if t not in seen:
            seen.add(t)
            kept.append((s, p, o))

    nodes_before = len({_normalize_node(s) for s, _, _ in kept} | {_normalize_node(o) for _, _, o in kept})
    progress("load", 1, 1, f"Loaded {n_raw} triples, {len(kept)} after exact dedup")

    if len(kept) <= 1:
        return Phase1Result(kept=kept, groups=[], triples_before=n_raw, nodes_before=nodes_before)

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        progress("embed", 0, 0, "sentence_transformers not installed")
        return Phase1Result(kept=kept, groups=[], triples_before=n_raw, nodes_before=nodes_before)

    progress("embed", 0, 1, "Loading embedding model…")
    model = SentenceTransformer(_EMBED_MODEL_NAME)
    phrases = [format_triple_phrase(s, p, o) for (s, p, o) in kept]
    embeddings = _embed_texts_with_cache(
        kg_path,
        model,
        _EMBED_MODEL_NAME,
        phrases,
        batch_size=batch_size,
        progress_callback=progress_callback,
        progress_phase="embed",
        progress_message="Embedding triples",
    )
    progress("top3", 0, 1, "Computing top-3 similar triples…")
    emb = np.array(embeddings, dtype=np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1
    emb_n = emb / norms
    n = len(kept)
    groups: list[LlmDedupGroup] = []
    for i in range(n):
        sims = np.dot(emb_n[i], emb_n.T)
        sims[i] = -2.0
        top3 = np.argsort(sims)[-3:][::-1].tolist()
        candidates = [phrases[j] for j in top3]
        scores = [float(sims[j]) for j in top3]
        groups.append(
            LlmDedupGroup(
                group_id=i,
                target=phrases[i],
                candidates=candidates,
                target_idx=i,
                candidate_indices=top3,
                scores=scores,
            )
        )
    progress("top3", 1, 1, f"Built {n} groups")
    return Phase1Result(kept=kept, groups=groups, triples_before=n_raw, nodes_before=nodes_before)


def _resolve_merge_conflicts(to_remove: set[int], canonical_of: dict[int, int]) -> None:
    """If two indices each say the other is canonical, keep the lower index (mutates to_remove)."""
    for i in list(to_remove):
        for j in list(to_remove):
            if i >= j:
                continue
            if canonical_of.get(i) == j and canonical_of.get(j) == i:
                to_remove.discard(j)


def _run_apply_write_sync(
    kg_path: Path,
    kept: list[tuple[str, str, str]],
    to_remove: set[int],
    removed_triples_audit: list[dict[str, Any]],
    triples_before: int,
    nodes_before: int,
    audit_dir: Path | None,
    run_id: str,
    started_at_iso: str,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Apply removals, write DB, write audit. Returns stats dict."""
    progress = progress_callback or (lambda *a: None)
    final_kept = [t for i, t in enumerate(kept) if i not in to_remove]
    nodes_after = len({_normalize_node(s) for s, _, _ in final_kept} | {_normalize_node(o) for _, _, o in final_kept})
    stats: dict[str, Any] = {
        "nodes_before": nodes_before,
        "nodes_after": nodes_after,
        "triples_before": triples_before,
        "triples_after": len(final_kept),
        "clusters_merged": 0,
        "removed_triples_count": len(removed_triples_audit),
        "bloat_saved_pct": round(100.0 * (triples_before - len(final_kept)) / triples_before, 2) if triples_before else 0,
        "merged_nodes": [],
        "removed_triples": removed_triples_audit,
    }

    progress("apply", 0, 1, "Applying changes…")
    conn = sqlite3.connect(str(kg_path))
    try:
        conn.execute("DELETE FROM triples")
        now = datetime.utcnow().isoformat() + "Z"
        for s, p, o in final_kept:
            conn.execute(
                "INSERT INTO triples (subject, predicate, object, created_at) VALUES (?, ?, ?, ?)",
                (s[:500], p[:200], o[:500], now),
            )
        conn.commit()
    finally:
        conn.close()
    progress("apply", 1, 1, "Done")

    finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    stats["run_id"] = run_id
    stats["started_at_iso"] = started_at_iso
    stats["finished_at_iso"] = finished_at
    stats["runtime_sec"] = 0

    if audit_dir is not None:
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / f"{run_id}.json"
        audit_data = {
            "run_id": run_id,
            "started_at_iso": started_at_iso,
            "finished_at_iso": finished_at,
            "stats": {k: v for k, v in stats.items() if k in ("nodes_before", "nodes_after", "triples_before", "triples_after", "clusters_merged", "removed_triples_count", "bloat_saved_pct", "runtime_sec")},
            "merged_nodes": stats["merged_nodes"],
            "removed_triples": removed_triples_audit,
        }
        try:
            audit_path.write_text(json.dumps(audit_data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"KG dedup: could not write audit file: {e}")

    return stats


async def run_kg_dedup_async(
    kg_path: Path,
    config: "Config",
    *,
    batch_size: int = 256,
    llm_batch_size: int = 20,
    progress_callback: ProgressCallback | None = None,
    audit_dir: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Top-3 + batched LLM dedup: load, exact dedup, embed, top-3 per triple,
    batched LLM merge decisions, resolve conflicts, apply and write.
    """
    t0 = time.perf_counter()
    rid = run_id or uuid.uuid4().hex[:12]
    started_at_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    loop = asyncio.get_event_loop()

    def do_phase1() -> Phase1Result:
        return _run_phase1_sync(
            kg_path, batch_size=batch_size, progress_callback=progress_callback
        )

    phase1 = await loop.run_in_executor(None, do_phase1)
    kept = phase1.kept
    groups = phase1.groups
    triples_before = phase1.triples_before
    nodes_before = phase1.nodes_before

    if triples_before == 0:
        return {
            "nodes_before": 0, "nodes_after": 0, "triples_before": 0, "triples_after": 0,
            "clusters_merged": 0, "removed_triples_count": 0, "bloat_saved_pct": 0.0,
            "runtime_sec": round(time.perf_counter() - t0, 2), "run_id": rid,
            "started_at_iso": "", "finished_at_iso": "", "merged_nodes": [], "removed_triples": [],
        }

    to_remove: set[int] = set()
    canonical_of: dict[int, int] = {}

    if groups:
        num_batches = (len(groups) + llm_batch_size - 1) // llm_batch_size
        for b in range(num_batches):
            start = b * llm_batch_size
            batch = groups[start : start + llm_batch_size]
            if progress_callback:
                progress_callback("llm_batch", b + 1, num_batches, f"LLM batch {b + 1}/{num_batches}…")
            decisions = await ask_llm_merge_decisions(reindex_batch(batch), config)
            tr, co = apply_decisions_to_batch(batch, decisions)
            to_remove |= tr
            canonical_of.update(co)
        _resolve_merge_conflicts(to_remove, canonical_of)

    removed_triples_audit: list[dict[str, Any]] = []
    for idx in to_remove:
        s, p, o = kept[idx]
        cidx = canonical_of.get(idx, idx)
        cs, cp, co = kept[cidx]
        removed_triples_audit.append({
            "subject": s, "predicate": p, "object": o,
            "merged_into": {"subject": cs, "predicate": cp, "object": co},
        })

    def do_apply_write() -> dict[str, Any]:
        return _run_apply_write_sync(
            kg_path,
            kept,
            to_remove,
            removed_triples_audit,
            triples_before,
            nodes_before,
            audit_dir,
            rid,
            started_at_iso,
            progress_callback,
        )

    result = await loop.run_in_executor(None, do_apply_write)
    result["runtime_sec"] = round(time.perf_counter() - t0, 2)
    if audit_dir is not None:
        audit_path = audit_dir / f"{rid}.json"
        if audit_path.exists():
            try:
                data = json.loads(audit_path.read_text(encoding="utf-8"))
                data["stats"]["runtime_sec"] = result["runtime_sec"]
                audit_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass
    return result


def run_kg_dedup_sync(
    kg_path: Path,
    config: "Config",
    *,
    batch_size: int = 256,
    llm_batch_size: int = 20,
    progress_callback: ProgressCallback | None = None,
    audit_dir: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Synchronous wrapper: runs run_kg_dedup_async via asyncio.run (for cron/bootstrap).
    """
    return asyncio.run(
        run_kg_dedup_async(
            kg_path,
            config,
            batch_size=batch_size,
            llm_batch_size=llm_batch_size,
            progress_callback=progress_callback,
            audit_dir=audit_dir,
            run_id=run_id,
        )
    )
