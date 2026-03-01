/**
 * Shared HTTP transport for the nanobot API.
 * All functions call relative /api/* paths (dev: Vite proxy, prod: same origin).
 */

export const BASE = '/api'

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${path} failed (${res.status}): ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}
