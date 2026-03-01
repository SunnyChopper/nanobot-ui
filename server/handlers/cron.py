"""Cron / scheduled jobs HTTP handlers."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException, Request

from server.models import (
    CronJobCreateRequest,
    CronJobItem,
    CronJobPatch,
    CronJobStateResponse,
    CronScheduleSummary,
)


def _cron_schedule_summary(schedule) -> CronScheduleSummary:
    """Build a display summary from nanobot CronSchedule."""
    kind = getattr(schedule, "kind", "every") or "every"
    if kind == "at" and getattr(schedule, "at_ms", None):
        ts = schedule.at_ms / 1000
        summary = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    elif kind == "every" and getattr(schedule, "every_ms", None):
        s = schedule.every_ms // 1000
        if s < 60:
            summary = f"Every {s}s"
        elif s < 3600:
            summary = f"Every {s // 60}m"
        else:
            summary = f"Every {s // 3600}h"
    elif kind == "cron" and getattr(schedule, "expr", None):
        summary = schedule.expr or ""
        if getattr(schedule, "tz", None):
            summary += f" ({schedule.tz})"
    else:
        summary = str(kind)
    return CronScheduleSummary(kind=kind, summary=summary)


def _cron_job_to_item(job) -> CronJobItem:
    """Convert nanobot CronJob to API CronJobItem."""
    state = getattr(job, "state", None)
    state_resp = CronJobStateResponse(
        next_run_at_ms=getattr(state, "next_run_at_ms", None) if state else None,
        last_run_at_ms=getattr(state, "last_run_at_ms", None) if state else None,
        last_status=getattr(state, "last_status", None) if state else None,
        last_error=getattr(state, "last_error", None) if state else None,
    )
    payload = getattr(job, "payload", None)
    message = getattr(payload, "message", "") if payload else ""
    kind = getattr(payload, "kind", None)
    is_system = (
        kind == "system_event"
        or (job.name == "memory_sleep" and kind == "memory_sleep")
    )
    return CronJobItem(
        id=job.id,
        name=job.name,
        enabled=job.enabled,
        schedule=_cron_schedule_summary(job.schedule),
        state=state_resp,
        message=message,
        is_system_job=is_system,
    )


def _parse_run_at_iso(iso: str) -> int | None:
    """Parse ISO datetime to ms since epoch. Returns None on failure."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


async def list_cron_jobs(request: Request, auth_user: object) -> list[CronJobItem]:
    """List all scheduled jobs (including disabled)."""
    cron = request.app.state.cron
    jobs = cron.list_jobs(include_disabled=True)
    return [_cron_job_to_item(j) for j in jobs]


async def create_cron_job(
    body: CronJobCreateRequest,
    request: Request,
    auth_user: object,
) -> CronJobItem:
    """Create a new scheduled job (prompt mode or workflow mode)."""
    from nanobot.cron.types import CronSchedule

    cron = request.app.state.cron
    name = body.name.strip()
    message = body.message.strip()
    if body.task_kind == "workflow" and body.workflow_id:
        name = f"workflow:{body.workflow_id.strip()}"
        message = json.dumps(body.workflow_input or {}, default=str)
    if body.schedule_kind == "at" and body.run_at_iso:
        at_ms = _parse_run_at_iso(body.run_at_iso)
        if at_ms is None:
            raise HTTPException(status_code=400, detail="Invalid run_at_iso datetime")
        schedule = CronSchedule(kind="at", at_ms=at_ms)
    elif body.schedule_kind == "cron" and body.cron_expr:
        schedule = CronSchedule(
            kind="cron",
            expr=body.cron_expr.strip(),
            tz=(body.cron_tz or "").strip() or None,
        )
    else:
        interval_ms = max(1, body.interval_minutes) * 60 * 1000
        schedule = CronSchedule(kind="every", every_ms=interval_ms)

    job = cron.add_job(
        name=name,
        schedule=schedule,
        message=message,
        delete_after_run=body.delete_after_run and body.schedule_kind == "at",
    )
    return _cron_job_to_item(job)


async def delete_cron_job(
    job_id: str, request: Request, auth_user: object
) -> None:
    """Remove a scheduled job by ID. System events cannot be deleted."""
    cron = request.app.state.cron
    job = cron.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if getattr(job.payload, "kind", None) == "system_event":
        raise HTTPException(
            status_code=403,
            detail="System events cannot be deleted. Disable or change schedule instead.",
        )
    removed = cron.remove_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


async def update_cron_job(
    job_id: str,
    body: CronJobPatch,
    request: Request,
    auth_user: object,
) -> CronJobItem:
    """Update a job: enable/disable and/or change schedule."""
    from nanobot.cron.types import CronSchedule

    cron = request.app.state.cron
    job = cron.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if body.enabled is not None:
        cron.enable_job(job_id, enabled=body.enabled)

    has_schedule = (
        body.schedule_kind is not None
        or body.cron_expr is not None
        or body.interval_minutes is not None
        or body.run_at_iso is not None
    )
    if has_schedule:
        kind = body.schedule_kind or job.schedule.kind
        if kind == "at" and (
            body.run_at_iso or getattr(job.schedule, "at_ms", None)
        ):
            at_ms = (
                _parse_run_at_iso(body.run_at_iso)
                if body.run_at_iso
                else job.schedule.at_ms
            )
            if at_ms is not None:
                schedule = CronSchedule(kind="at", at_ms=at_ms)
                cron.update_schedule(job_id, schedule)
        elif kind == "cron":
            expr = (
                body.cron_expr or getattr(job.schedule, "expr", None) or ""
            ).strip()
            if expr:
                tz = (
                    body.cron_tz or getattr(job.schedule, "tz", None) or ""
                ).strip() or None
                schedule = CronSchedule(kind="cron", expr=expr, tz=tz)
                cron.update_schedule(job_id, schedule)
        elif kind == "every":
            if body.interval_minutes is not None:
                interval_ms = max(1, body.interval_minutes) * 60 * 1000
            else:
                interval_ms = getattr(job.schedule, "every_ms", None) or 3600000
            schedule = CronSchedule(kind="every", every_ms=interval_ms)
            cron.update_schedule(job_id, schedule)

    job = cron.get_job(job_id)
    return _cron_job_to_item(job)


async def run_cron_job(
    job_id: str,
    request: Request,
    auth_user: object,
) -> dict:
    """Run a cron job now (manual trigger). Uses force=True so disabled jobs can be run."""
    cron = request.app.state.cron
    job = cron.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    ok = await cron.run_job(job_id, force=True)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail="Job execution did not complete (check server logs).",
        )
    return {"ok": True, "job_id": job_id}
