/** Memory API: MEMORY.md / HISTORY.md and long-term chunks */

import { apiFetch } from './http'
import type {
  MemoryChunksListResponse,
  MemoryChunkItem,
  MemoryResponse,
  ScanIrrelevantHistoryResponse,
  VerifyBulletResponse,
} from './types'

export function getMemory(): Promise<MemoryResponse> {
  return apiFetch('/memory')
}

export function putMemoryLongTerm(content: string): Promise<{ status: string }> {
  return apiFetch('/memory/long-term', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

export function putMemoryHistory(content: string): Promise<{ status: string }> {
  return apiFetch('/memory/history', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

export function appendMemoryHistory(entry: string): Promise<{ status: string }> {
  return apiFetch('/memory/history/append', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entry }),
  })
}

export function verifyBullet(text: string): Promise<VerifyBulletResponse> {
  return apiFetch('/memory/tasks/verify-bullet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
}

export function scanIrrelevantHistory(): Promise<ScanIrrelevantHistoryResponse> {
  return apiFetch('/memory/tasks/scan-irrelevant-history', { method: 'POST' })
}

export function removeHistoryEntries(
  indices: number[],
): Promise<{ status: string; removed: number }> {
  return apiFetch('/memory/history/remove-entries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ indices }),
  })
}

export function getMemoryChunks(params?: {
  limit?: number
  offset?: number
  run_id?: string
  date?: string
}): Promise<MemoryChunksListResponse> {
  const sp = new URLSearchParams()
  if (params?.limit != null) sp.set('limit', String(params.limit))
  if (params?.offset != null) sp.set('offset', String(params.offset))
  if (params?.run_id != null) sp.set('run_id', params.run_id)
  if (params?.date != null) sp.set('date', params.date)
  const q = sp.toString()
  return apiFetch(`/memory/chunks${q ? `?${q}` : ''}`)
}

export function getMemoryChunk(id: string): Promise<MemoryChunkItem> {
  return apiFetch(`/memory/chunks/${encodeURIComponent(id)}`)
}

export function updateMemoryChunk(
  id: string,
  document: string,
): Promise<{ status: string }> {
  return apiFetch(`/memory/chunks/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document }),
  })
}

export function deleteMemoryChunks(
  ids: string[],
): Promise<{ status: string; deleted: number }> {
  return apiFetch('/memory/chunks', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  })
}
