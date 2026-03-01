/** Allowlist (tool approval) API */

import { apiFetch } from './http'
import type { AllowlistResponse } from './types'

export function getAllowlist(): Promise<AllowlistResponse> {
  return apiFetch('/allowlist')
}

export function addAllowlistEntry(
  tool: string,
  pattern: string,
): Promise<{ status: string; tool: string; pattern: string }> {
  return apiFetch('/allowlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool, pattern }),
  })
}

export function removeAllowlistEntry(
  tool: string,
  pattern: string,
): Promise<{ status: string; tool: string; pattern: string }> {
  return apiFetch('/allowlist', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool, pattern }),
  })
}
