import { useCallback, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getMemoryChunks,
  updateMemoryChunk,
  deleteMemoryChunks,
} from '../api/client'
import type { MemoryChunkItem } from '../api/types'

const PAGE_SIZE = 20

function ordinal(n: number): string {
  const s = n % 100
  if (s >= 11 && s <= 13) return `${n}th`
  switch (n % 10) {
    case 1: return `${n}st`
    case 2: return `${n}nd`
    case 3: return `${n}rd`
    default: return `${n}th`
  }
}

function formatChunkDateWithAgo(raw: string | undefined): string {
  if (raw == null || raw === '') return ''
  const m = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/.exec(String(raw))
  if (!m) return String(raw)
  const y = parseInt(m[1], 10)
  const mo = parseInt(m[2], 10) - 1
  const d = parseInt(m[3], 10)
  const h = parseInt(m[4], 10)
  const min = parseInt(m[5], 10)
  const date = new Date(Date.UTC(y, mo, d, h, min, 0))
  const now = new Date()
  const absFormatted = `${date.toLocaleString(undefined, { month: 'short' })} ${ordinal(date.getDate())}, ${date.getFullYear()} at ${date.toLocaleString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true })}`
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffH = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffH / 24)
  const diffMonth = Math.floor(diffDay / 30)
  const diffYear = Math.floor(diffDay / 365)
  let ago = ''
  if (diffYear >= 1) ago = `${diffYear} ${diffYear === 1 ? 'year' : 'years'} ago`
  else if (diffMonth >= 1) ago = `${diffMonth} ${diffMonth === 1 ? 'month' : 'months'} ago`
  else if (diffDay >= 1) ago = `${diffDay} ${diffDay === 1 ? 'day' : 'days'} ago`
  else if (diffH >= 1) ago = `${diffH} ${diffH === 1 ? 'hour' : 'hours'} ago`
  else if (diffMin >= 1) ago = `${diffMin} ${diffMin === 1 ? 'minute' : 'minutes'} ago`
  else if (diffSec >= 1) ago = `${diffSec} ${diffSec === 1 ? 'second' : 'seconds'} ago`
  else ago = 'just now'
  return ago ? `${absFormatted} (${ago})` : absFormatted
}

export function LongTermChunksView() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deleting, setDeleting] = useState(false)

  const [mutationError, setMutationError] = useState<string | null>(null)
  const { data, isLoading: loading, error: queryError, isError: hasError } = useQuery({
    queryKey: ['memory', 'chunks', page],
    queryFn: () => getMemoryChunks({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  })
  const chunks = data?.chunks ?? []
  const total = data?.total ?? 0
  const error = hasError ? String((queryError as Error)?.message ?? queryError) : mutationError

  const handleSaveEdit = async () => {
    if (!editingId || saving) return
    setSaving(true)
    try {
      await updateMemoryChunk(editingId, editDraft)
      setEditingId(null)
      queryClient.invalidateQueries({ queryKey: ['memory', 'chunks'] })
    } catch (e) {
      setMutationError(String((e as Error)?.message ?? e))
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteSelected = async () => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0 || deleting) return
    if (!window.confirm(`Delete ${ids.length} chunk(s)?`)) return
    setDeleting(true)
    try {
      await deleteMemoryChunks(ids)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['memory', 'chunks'] })
    } catch (e) {
      setMutationError(String((e as Error)?.message ?? e))
    } finally {
      setDeleting(false)
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const startEdit = (chunk: MemoryChunkItem) => {
    setEditingId(chunk.id)
    setEditDraft(chunk.document)
  }

  if (loading && chunks.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-zinc-500 text-sm animate-pulse">
        Loading chunks…
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-zinc-950">
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide">
          Long-term memory chunks ({total})
        </h2>
        {selectedIds.size > 0 && (
          <button
            type="button"
            onClick={handleDeleteSelected}
            disabled={deleting}
            className="px-3 py-1.5 rounded bg-red-900/60 hover:bg-red-800/60 text-red-200 text-sm disabled:opacity-50"
          >
            {deleting ? 'Deleting…' : `Delete ${selectedIds.size} selected`}
          </button>
        )}
      </div>
      {error && (
        <div className="mx-4 mt-2 rounded-lg border border-red-800 bg-red-950/50 p-3 text-sm text-red-300">
          {error}
        </div>
      )}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-4 space-y-3 relative">
        {(deleting || (loading && chunks.length > 0)) && (
          <div
            className="absolute inset-0 bg-zinc-950/70 flex items-center justify-center z-10"
            aria-busy
          >
            <div className="flex flex-col items-center gap-2 text-zinc-400 text-sm">
              <div className="w-6 h-6 border-2 border-zinc-500 border-t-zinc-300 rounded-full animate-spin" />
              {deleting ? 'Deleting…' : 'Loading…'}
            </div>
          </div>
        )}
        {chunks.length === 0 && !loading ? (
          <p className="text-zinc-500 text-sm">No chunks yet. Run memory sleep to consolidate.</p>
        ) : (
          chunks.map((chunk) => (
            <div
              key={chunk.id}
              className="rounded-lg border border-zinc-800 bg-zinc-900/80 p-4"
            >
              <div className="flex items-start gap-2 mb-2">
                <input
                  type="checkbox"
                  checked={selectedIds.has(chunk.id)}
                  onChange={() => toggleSelect(chunk.id)}
                  className="mt-1 rounded border-zinc-600"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-zinc-500 mb-1 flex items-center gap-2 flex-wrap">
                    {chunk.id.startsWith('sleep_') && (
                      <span className="rounded px-1.5 py-0.5 bg-zinc-700 text-zinc-300 text-xs font-medium">
                        Sleep
                      </span>
                    )}
                    {chunk.metadata?.date != null && chunk.metadata.date !== '' && (
                      <span>{formatChunkDateWithAgo(String(chunk.metadata.date))}</span>
                    )}
                  </div>
                  {editingId === chunk.id ? (
                    <div>
                      <textarea
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        className="w-full rounded border border-zinc-700 bg-zinc-800 p-2 text-sm text-zinc-200 min-h-[80px]"
                      />
                      <div className="flex gap-2 mt-2">
                        <button
                          type="button"
                          onClick={handleSaveEdit}
                          disabled={saving}
                          className="px-2 py-1 rounded bg-zinc-700 text-zinc-200 text-xs disabled:opacity-50"
                        >
                          {saving ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingId(null)}
                          disabled={saving}
                          className="px-2 py-1 rounded bg-zinc-800 text-zinc-400 text-xs"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-zinc-300 whitespace-pre-wrap">
                      {chunk.document.slice(0, 300)}
                      {chunk.document.length > 300 ? '…' : ''}
                    </p>
                  )}
                </div>
                {editingId !== chunk.id && (
                  <button
                    type="button"
                    onClick={() => startEdit(chunk)}
                    className="text-xs text-zinc-500 hover:text-zinc-300 shrink-0"
                  >
                    Edit
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-2 py-3 border-t border-zinc-800">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1 rounded bg-zinc-800 text-zinc-300 text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs text-zinc-500">
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => p + 1)}
            disabled={(page + 1) * PAGE_SIZE >= total}
            className="px-3 py-1 rounded bg-zinc-800 text-zinc-300 text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
