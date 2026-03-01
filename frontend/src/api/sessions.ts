/** Session API: list, get, delete, rename, new, branch, retry, edit, set project */

import { apiFetch } from './http'
import type { SessionDetail, SessionListItem } from './types/sessions'

/** List all sessions, sorted newest-first. Optional search query filters by title, chat_id, or key. */
export function getSessions(q?: string): Promise<SessionListItem[]> {
  const params = q?.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''
  return apiFetch(`/sessions${params}`)
}

/** Get full history for a session. The key may contain ':', URL-encode it. */
export function getSession(key: string): Promise<SessionDetail> {
  return apiFetch(`/sessions/${encodeURIComponent(key)}`)
}

/** Permanently delete a session (removes file from disk). */
export function deleteSession(key: string): Promise<{ status: string; key: string }> {
  return apiFetch(`/sessions/${encodeURIComponent(key)}`, { method: 'DELETE' })
}

/** Rename a session by setting a human-readable title. */
export function renameSession(
  key: string,
  title: string,
): Promise<{ status: string; key: string; title: string }> {
  return apiFetch(`/sessions/${encodeURIComponent(key)}/rename`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

/** Pop the last assistant message so the frontend can retry. */
export function retrySession(
  key: string,
): Promise<{ status: string; key: string; message_count: number }> {
  return apiFetch(`/sessions/${encodeURIComponent(key)}/retry`, { method: 'POST' })
}

/** Truncate the session to messageIndex (exclusive) so the frontend can re-send an edited user message. */
export function editSessionMessage(
  key: string,
  messageIndex: number,
  newContent: string,
): Promise<{ status: string; key: string; message_count: number }> {
  return apiFetch(`/sessions/${encodeURIComponent(key)}/edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message_index: messageIndex, new_content: newContent }),
  })
}

/** Start a new conversation (clears history). */
export function newSession(key: string): Promise<{ status: string; key: string }> {
  return apiFetch(`/sessions/${encodeURIComponent(key)}/new`, { method: 'POST' })
}

/** Branch from a message: copy messages[0..messageIndex] into a new session. Returns the new session key. */
export function branchSession(
  key: string,
  messageIndex: number,
): Promise<{ status: string; key: string; message_count: number }> {
  return apiFetch(`/sessions/${encodeURIComponent(key)}/branch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message_index: messageIndex }),
  })
}

/** Set or clear the active project for a session. */
export function setSessionProject(
  sessionKey: string,
  project: string | null,
): Promise<{ status: string; key: string; project: string | null }> {
  return apiFetch(`/sessions/${encodeURIComponent(sessionKey)}/project`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project }),
  })
}
