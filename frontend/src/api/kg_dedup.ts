/** KG dedup (Admin) API */

import { BASE, apiFetch } from './http'
import type {
  KgDedupAuditDetail,
  KgDedupAuditListItem,
  KgDedupProgressEvent,
  KgDedupRunResponse,
} from './types'

export function startKgDedup(): Promise<KgDedupRunResponse> {
  return apiFetch('/kg-dedup/run', { method: 'POST' })
}

export async function streamKgDedupProgress(
  runId: string,
  onEvent: (event: KgDedupProgressEvent) => void,
): Promise<void> {
  const res = await fetch(
    `${BASE}/kg-dedup/stream?run_id=${encodeURIComponent(runId)}`,
    {
      credentials: 'include',
      headers: { Accept: 'text/event-stream' },
    },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(
      (data as { detail?: string }).detail || `Stream failed (${res.status})`,
    )
  }
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split(/\n\n+/)
    buffer = events.pop() ?? ''
    for (const block of events) {
      const line = block.split('\n').find((l) => l.startsWith('data: '))
      if (line) {
        try {
          const data = JSON.parse(line.slice(6)) as KgDedupProgressEvent
          onEvent(data)
          if (data.done) return
        } catch {
          // skip invalid JSON
        }
      }
    }
  }
  const line = buffer.split('\n').find((l) => l.startsWith('data: '))
  if (line) {
    try {
      const data = JSON.parse(line.slice(6)) as KgDedupProgressEvent
      onEvent(data)
    } catch {
      // skip
    }
  }
}

export function listKgDedupAudits(): Promise<KgDedupAuditListItem[]> {
  return apiFetch('/kg-dedup/audit')
}

export function getKgDedupAudit(runId: string): Promise<KgDedupAuditDetail> {
  return apiFetch(`/kg-dedup/audit/${encodeURIComponent(runId)}`)
}

export function restoreKgDedupTriple(triple: {
  subject: string
  predicate: string
  object: string
}): Promise<{ status: string; inserted: boolean }> {
  return apiFetch('/kg-dedup/restore', {
    method: 'POST',
    body: JSON.stringify(triple),
    headers: { 'Content-Type': 'application/json' },
  })
}
