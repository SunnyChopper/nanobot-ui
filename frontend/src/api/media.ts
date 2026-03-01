/** Media API: upload attachments */

import { BASE } from './http'

export function uploadAttachment(file: File): Promise<{ path: string }> {
  const form = new FormData()
  form.append('file', file)
  return fetch(`${BASE}/upload`, {
    method: 'POST',
    body: form,
  }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new Error(`Upload failed (${res.status}): ${text}`)
    }
    return res.json() as Promise<{ path: string }>
  })
}
