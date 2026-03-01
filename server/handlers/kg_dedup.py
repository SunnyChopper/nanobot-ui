"""KG dedup HTTP handlers: run, stream progress, audit, restore."""

from __future__ import annotations

import asyncio
import json
import queue
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from nanobot.config.loader import get_data_dir
from server.kg_dedup import run_kg_dedup_async
from server.models import KgDedupRestoreRequest


def _kg_dedup_run_store(request: Request) -> dict:
    """Get the kg_dedup_runs store from app state."""
    return getattr(request.app.state, "kg_dedup_runs", {})


async def start_kg_dedup(request: Request, auth_user: object) -> dict:
    """Start KG deduplication in the background. Returns run_id; client uses stream for progress."""
    config = request.app.state.config
    data_dir = get_data_dir()
    kg_path = data_dir / "memory" / "knowledge_graph.db"
    audit_dir = data_dir / "memory" / "kg_dedup_audit"
    kg_cfg = getattr(config, "kg_dedup", None)
    batch_size = getattr(kg_cfg, "batch_size", 256) if kg_cfg else 256
    llm_batch_size = getattr(kg_cfg, "llm_batch_size", 20) if kg_cfg else 20

    run_id = uuid.uuid4().hex[:12]
    progress_queue: queue.Queue = queue.Queue()

    store = _kg_dedup_run_store(request)
    store[run_id] = progress_queue

    def progress_callback(phase: str, current: int, total: int, message: str) -> None:
        progress_queue.put(
            {"phase": phase, "step": current, "total": total, "message": message}
        )

    async def run_dedup_and_finish() -> None:
        try:
            result = await run_kg_dedup_async(
                kg_path,
                config,
                batch_size=batch_size,
                llm_batch_size=llm_batch_size,
                progress_callback=progress_callback,
                audit_dir=audit_dir,
                run_id=run_id,
            )
            progress_queue.put({"done": True, "run_id": run_id, "stats": result})
        except Exception as e:
            progress_queue.put({"done": True, "run_id": run_id, "error": str(e)})
        finally:
            progress_queue.put(None)
            store.pop(run_id, None)

    asyncio.create_task(run_dedup_and_finish())
    return {"run_id": run_id, "status": "started"}


async def stream_kg_dedup_progress(
    request: Request,
    run_id: str,
    auth_user: object,
):
    """SSE stream of progress events for a KG dedup run."""
    store = _kg_dedup_run_store(request)
    progress_queue = store.get(run_id)
    if progress_queue is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Run not found or already finished",
                "run_id": run_id,
            },
        )

    async def event_generator():
        loop = asyncio.get_event_loop()
        q = progress_queue

        def get_item():
            return q.get(timeout=2.0)

        while True:
            try:
                item = await loop.run_in_executor(None, get_item)
            except queue.Empty:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                continue
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def list_kg_dedup_audits(request: Request, auth_user: object) -> list:
    """List recent KG dedup runs (from audit files)."""
    data_dir = get_data_dir()
    audit_dir = data_dir / "memory" / "kg_dedup_audit"
    if not audit_dir.exists():
        return []
    items = []
    for p in sorted(
        audit_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True
    )[:50]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            items.append(
                {
                    "run_id": data.get("run_id", p.stem),
                    "started_at_iso": data.get("started_at_iso"),
                    "finished_at_iso": data.get("finished_at_iso"),
                    "stats": data.get("stats", {}),
                }
            )
        except Exception:
            continue
    return items


async def get_kg_dedup_audit(
    run_id: str,
    request: Request,
    auth_user: object,
) -> dict:
    """Get full audit for a run (merged_nodes, removed_triples)."""
    data_dir = get_data_dir()
    audit_path = data_dir / "memory" / "kg_dedup_audit" / f"{run_id}.json"
    if not audit_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Audit for run {run_id} not found"
        )
    try:
        return json.loads(audit_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def restore_kg_dedup_triple(
    body: KgDedupRestoreRequest,
    auth_user: object,
) -> dict:
    """Restore a triple that was removed during dedup."""
    from server.knowledge import add_triple

    inserted = add_triple(body.subject, body.predicate, body.object)
    return {"status": "ok", "inserted": inserted}
