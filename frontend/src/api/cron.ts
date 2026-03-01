/** Cron / scheduled jobs API */

import { apiFetch } from './http'
import type { CronJobItem } from './types'

export function getCronJobs(): Promise<CronJobItem[]> {
  return apiFetch('/cron/jobs')
}

export function createCronJob(payload: {
  name: string
  message: string
  task_kind?: 'prompt' | 'workflow'
  workflow_id?: string | null
  workflow_input?: Record<string, unknown> | null
  schedule_kind?: 'every' | 'at' | 'cron'
  interval_minutes?: number
  run_at_iso?: string | null
  cron_expr?: string | null
  cron_tz?: string | null
  delete_after_run?: boolean
}): Promise<CronJobItem> {
  const body: Record<string, unknown> = {
    name: payload.name,
    message: payload.message,
    schedule_kind: payload.schedule_kind ?? 'every',
    interval_minutes: payload.interval_minutes ?? 60,
  }
  if (payload.task_kind != null) body.task_kind = payload.task_kind
  if (payload.workflow_id != null) body.workflow_id = payload.workflow_id || null
  if (payload.workflow_input != null) body.workflow_input = payload.workflow_input || null
  if (payload.run_at_iso != null) body.run_at_iso = payload.run_at_iso || null
  if (payload.cron_expr != null) body.cron_expr = payload.cron_expr || null
  if (payload.cron_tz != null) body.cron_tz = payload.cron_tz || null
  if (payload.delete_after_run != null) body.delete_after_run = payload.delete_after_run
  return apiFetch('/cron/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function deleteCronJob(jobId: string): Promise<void> {
  return apiFetch(`/cron/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' })
}

export function updateCronJobEnabled(
  jobId: string,
  enabled: boolean,
): Promise<CronJobItem> {
  return apiFetch(`/cron/jobs/${encodeURIComponent(jobId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  })
}

export function updateCronJobSchedule(
  jobId: string,
  patch: {
    schedule_kind?: 'every' | 'at' | 'cron'
    cron_expr?: string | null
    cron_tz?: string | null
    interval_minutes?: number
    run_at_iso?: string | null
  },
): Promise<CronJobItem> {
  const body: Record<string, unknown> = {}
  if (patch.schedule_kind != null) body.schedule_kind = patch.schedule_kind
  if (patch.cron_expr != null) body.cron_expr = patch.cron_expr
  if (patch.cron_tz != null) body.cron_tz = patch.cron_tz
  if (patch.interval_minutes != null) body.interval_minutes = patch.interval_minutes
  if (patch.run_at_iso != null) body.run_at_iso = patch.run_at_iso
  return apiFetch(`/cron/jobs/${encodeURIComponent(jobId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function runCronJob(jobId: string): Promise<{ ok: boolean; job_id: string }> {
  return apiFetch(`/cron/jobs/${encodeURIComponent(jobId)}/run`, {
    method: 'POST',
  })
}
