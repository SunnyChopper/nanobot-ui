import { useCallback, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getMemory,
  putMemoryLongTerm,
  putMemoryHistory,
  appendMemoryHistory,
  verifyBullet,
  scanIrrelevantHistory,
  removeHistoryEntries,
} from '../api/client'
import type { MemoryResponse, VerifyBulletResponse } from '../api/types'
import { LongTermChunksView } from './LongTermChunksView'
import { KnowledgeBasePage, type KnowledgeSubTab } from './KnowledgeBasePage'
import { MemoryEditor } from './organisms/MemoryEditor'
import { HistoryEditor } from './organisms/HistoryEditor'

type MemoryTab = 'files' | 'chunks' | 'knowledge'

export function MemoryPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<MemoryTab>('files')
  const [knowledgeSubTab, setKnowledgeSubTab] = useState<KnowledgeSubTab>('triples')
  const {
    data: memoryData,
    isLoading: loading,
    isError: hasError,
    error: queryError,
  } = useQuery({
    queryKey: ['memory'],
    queryFn: getMemory,
  })
  const data = memoryData ?? null
  const [error, setError] = useState<string | null>(null)
  const displayError = hasError ? String((queryError as Error)?.message ?? queryError) : error

  const [editMemory, setEditMemory] = useState(false)
  const [editHistory, setEditHistory] = useState(false)
  const [memoryDraft, setMemoryDraft] = useState('')
  const [historyDraft, setHistoryDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [appendEntry, setAppendEntry] = useState('')
  const [appending, setAppending] = useState(false)

  const [verifyText, setVerifyText] = useState('')
  const [verifyResult, setVerifyResult] = useState<VerifyBulletResponse | null>(null)
  const [verifyLoading, setVerifyLoading] = useState(false)

  const [scanIndices, setScanIndices] = useState<number[] | null>(null)
  const [scanReasons, setScanReasons] = useState<Record<number, string>>({})
  const [scanLoading, setScanLoading] = useState(false)
  const [selectedToRemove, setSelectedToRemove] = useState<Set<number>>(new Set())
  const [removing, setRemoving] = useState(false)

  const fetchMemorySilent = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['memory'] })
  }, [queryClient])

  const handleSaveMemory = async () => {
    if (saving) return
    setSaving(true)
    setSaveError(null)
    try {
      await putMemoryLongTerm(memoryDraft)
      setEditMemory(false)
      queryClient.setQueryData<MemoryResponse>(['memory'], (d) => (d ? { ...d, memory: memoryDraft } : d))
    } catch (e) {
      setSaveError(String(e instanceof Error ? e.message : e))
    } finally {
      setSaving(false)
    }
  }

  const handleCancelMemory = () => {
    setMemoryDraft(data?.memory ?? '')
    setEditMemory(false)
    setSaveError(null)
  }

  const handleSaveHistory = async () => {
    if (saving) return
    setSaving(true)
    setSaveError(null)
    try {
      await putMemoryHistory(historyDraft)
      setEditHistory(false)
      queryClient.setQueryData<MemoryResponse>(['memory'], (d) => (d ? { ...d, history: historyDraft } : d))
      setScanIndices(null)
      setScanReasons({})
    } catch (e) {
      setSaveError(String(e instanceof Error ? e.message : e))
    } finally {
      setSaving(false)
    }
  }

  const handleCancelHistory = () => {
    setHistoryDraft(data?.history ?? '')
    setEditHistory(false)
    setSaveError(null)
  }

  const handleAppend = async () => {
    if (!appendEntry.trim() || appending) return
    const d = new Date()
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    const formatted = `${y}-${m}-${day} ${h}:${min}`
    const payload = `\n\n[${formatted}] ${appendEntry.trim()}`
    setAppending(true)
    try {
      await appendMemoryHistory(payload)
      setAppendEntry('')
      queryClient.invalidateQueries({ queryKey: ['memory'] })
    } finally {
      setAppending(false)
    }
  }

  const handleVerify = async () => {
    if (!verifyText.trim() || verifyLoading) return
    setVerifyLoading(true)
    setVerifyResult(null)
    try {
      const res = await verifyBullet(verifyText.trim())
      setVerifyResult(res)
    } catch (e) {
      setVerifyResult({ verified: false, comment: String(e instanceof Error ? e.message : e) })
    } finally {
      setVerifyLoading(false)
    }
  }

  const handleScan = async () => {
    if (scanLoading) return
    setScanLoading(true)
    setScanIndices(null)
    setScanReasons({})
    setSelectedToRemove(new Set())
    try {
      const res = await scanIrrelevantHistory()
      setScanIndices(res.irrelevant_indices ?? [])
      setScanReasons(res.reasons ?? {})
    } finally {
      setScanLoading(false)
    }
  }

  const handleRemoveSelected = async () => {
    const indices = Array.from(selectedToRemove)
    if (indices.length === 0 || removing) return
    if (!window.confirm(`Remove ${indices.length} selected history entries?`)) return
    setRemoving(true)
    try {
      await removeHistoryEntries(indices)
      setScanIndices(null)
      setScanReasons({})
      setSelectedToRemove(new Set())
      fetchMemorySilent()
    } finally {
      setRemoving(false)
    }
  }

  const toggleRemoveIndex = (i: number) => {
    setSelectedToRemove((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  useEffect(() => {
    if (data && editMemory) setMemoryDraft(data.memory)
  }, [data?.memory, editMemory])
  useEffect(() => {
    if (data && editHistory) setHistoryDraft(data.history)
  }, [data?.history, editHistory])

  if (tab === 'chunks') {
    return (
      <div className="flex flex-1 flex-col overflow-hidden bg-zinc-950">
        <div className="flex gap-1 border-b border-zinc-800 px-4">
          <button
            type="button"
            onClick={() => setTab('files')}
            className="px-3 py-2 text-sm text-zinc-500 hover:text-zinc-300 border-b-2 border-transparent -mb-px"
          >
            MEMORY & History
          </button>
          <button
            type="button"
            onClick={() => setTab('chunks')}
            className="px-3 py-2 text-sm text-zinc-200 border-b-2 border-zinc-400 -mb-px"
          >
            Long-term chunks
          </button>
          <button
            type="button"
            onClick={() => setTab('knowledge')}
            className="px-3 py-2 text-sm text-zinc-500 hover:text-zinc-300 border-b-2 border-transparent -mb-px"
          >
            Knowledge base
          </button>
        </div>
        <LongTermChunksView />
      </div>
    )
  }

  if (tab === 'knowledge') {
    return (
      <div className="flex flex-1 flex-col overflow-hidden bg-zinc-950">
        <div className="flex gap-1 border-b border-zinc-800 px-4">
          <button
            type="button"
            onClick={() => setTab('files')}
            className="px-3 py-2 text-sm text-zinc-500 hover:text-zinc-300 border-b-2 border-transparent -mb-px"
          >
            MEMORY & History
          </button>
          <button
            type="button"
            onClick={() => setTab('chunks')}
            className="px-3 py-2 text-sm text-zinc-500 hover:text-zinc-300 border-b-2 border-transparent -mb-px"
          >
            Long-term chunks
          </button>
          <button
            type="button"
            onClick={() => setTab('knowledge')}
            className="px-3 py-2 text-sm text-zinc-200 border-b-2 border-zinc-400 -mb-px"
          >
            Knowledge base
          </button>
        </div>
        <KnowledgeBasePage
          subTab={knowledgeSubTab}
          onSubTabChange={setKnowledgeSubTab}
        />
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center text-zinc-500 text-sm animate-pulse">
        Loading memory…
      </div>
    )
  }
  if (displayError) {
    return (
      <div className="flex flex-1 items-center justify-center text-red-400 text-sm">
        {displayError}
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-zinc-950">
      <div className="flex gap-1 border-b border-zinc-800 px-4">
        <button
          type="button"
          onClick={() => setTab('files')}
          className="px-3 py-2 text-sm text-zinc-200 border-b-2 border-zinc-400 -mb-px"
        >
          MEMORY & History
        </button>
        <button
          type="button"
          onClick={() => setTab('chunks')}
          className="px-3 py-2 text-sm text-zinc-500 hover:text-zinc-300 border-b-2 border-transparent -mb-px"
        >
          Long-term chunks
        </button>
        <button
          type="button"
          onClick={() => setTab('knowledge')}
          className="px-3 py-2 text-sm text-zinc-500 hover:text-zinc-300 border-b-2 border-transparent -mb-px"
        >
          Knowledge base
        </button>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-6 space-y-8">
        {saveError && (
          <div className="rounded-lg border border-red-800 bg-red-950/50 p-3 text-sm text-red-300">
            {saveError}
          </div>
        )}

        <MemoryEditor
          title="Long-term memory (MEMORY.md)"
          value={data?.memory ?? ''}
          draft={memoryDraft}
          editing={editMemory}
          saving={saving}
          onEdit={() => {
            setEditMemory(true)
            setMemoryDraft(data?.memory ?? '')
          }}
          onDraftChange={setMemoryDraft}
          onSave={handleSaveMemory}
          onCancel={handleCancelMemory}
        />

        {/* Verify bullet */}
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
          <h3 className="text-sm font-medium text-zinc-400 mb-2">Verify with AI</h3>
          <p className="text-xs text-zinc-500 mb-2">
            Paste a bullet or sentence from memory to check if it is still accurate.
          </p>
          <div className="flex gap-2 flex-wrap items-end">
            <input
              type="text"
              value={verifyText}
              onChange={(e) => setVerifyText(e.target.value)}
              placeholder="e.g. User prefers dark mode"
              className="flex-1 min-w-[200px] rounded border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500"
            />
            <button
              type="button"
              onClick={handleVerify}
              disabled={verifyLoading || !verifyText.trim()}
              className="px-3 py-2 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm disabled:opacity-50"
            >
              {verifyLoading ? 'Checking…' : 'Verify'}
            </button>
          </div>
          {verifyResult && (
            <div
              className={`mt-3 p-3 rounded text-sm ${
                verifyResult.verified
                  ? 'bg-emerald-950/50 border border-emerald-800 text-emerald-200'
                  : 'bg-amber-950/50 border border-amber-800 text-amber-200'
              }`}
            >
              <strong>{verifyResult.verified ? 'Verified' : 'Not verified'}</strong>
              {verifyResult.comment && ` — ${verifyResult.comment}`}
            </div>
          )}
        </section>

        <HistoryEditor
          title="History log (HISTORY.md)"
          value={data?.history ?? ''}
          draft={historyDraft}
          editing={editHistory}
          saving={saving}
          onEdit={() => {
            setEditHistory(true)
            setHistoryDraft(data?.history ?? '')
          }}
          onDraftChange={setHistoryDraft}
          onSave={handleSaveHistory}
          onCancel={handleCancelHistory}
        />

        {/* Append to history */}
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
          <h3 className="text-sm font-medium text-zinc-400 mb-2">Append to history</h3>
          <div className="flex gap-2">
            <input
              type="text"
              value={appendEntry}
              onChange={(e) => setAppendEntry(e.target.value)}
              placeholder="Note or summary…"
              className="flex-1 rounded border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500"
            />
            <button
              type="button"
              onClick={handleAppend}
              disabled={appending || !appendEntry.trim()}
              className="px-3 py-2 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm disabled:opacity-50"
            >
              {appending ? 'Appending…' : 'Append'}
            </button>
          </div>
        </section>

        {/* Scan irrelevant history */}
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
          <h3 className="text-sm font-medium text-zinc-400 mb-2">Scan for irrelevant history</h3>
          <p className="text-xs text-zinc-500 mb-2">
            Ask AI to suggest history entries that may be irrelevant or redundant.
          </p>
          <div className="flex flex-wrap gap-2 items-center">
            <button
              type="button"
              onClick={handleScan}
              disabled={scanLoading}
              className="px-3 py-2 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm disabled:opacity-50"
            >
              {scanLoading ? 'Scanning…' : 'Scan'}
            </button>
            {scanIndices && scanIndices.length > 0 && (
              <button
                type="button"
                onClick={() => setSelectedToRemove(new Set(scanIndices))}
                className="px-3 py-2 rounded bg-zinc-600 hover:bg-zinc-500 text-zinc-200 text-sm"
              >
                Select All
              </button>
            )}
            {scanIndices && scanIndices.length > 0 && (() => {
              const entries = (data?.history ?? '').split(/\n\n/).map((e) => e.trim()).filter(Boolean)
              return (
                <>
                  <div className="w-full mt-2 space-y-2">
                    {scanIndices.map((idx) => {
                      const text = entries[idx] ?? ''
                      const preview = text.length > 200 ? `${text.slice(0, 200)}…` : text
                      const reason = (scanReasons as Record<number | string, string>)[idx] ?? (scanReasons as Record<number | string, string>)[String(idx)]
                      return (
                        <div
                          key={idx}
                          className={`flex items-start gap-2 rounded border p-3 transition-colors cursor-pointer select-none hover:bg-zinc-700/80 focus-within:ring-2 focus-within:ring-amber-500/50 ${
                            selectedToRemove.has(idx)
                              ? 'border-amber-500/60 bg-amber-950/20'
                              : 'border-zinc-700 bg-zinc-800/80'
                          }`}
                          onClick={() => toggleRemoveIndex(idx)}
                        >
                          <input
                            type="checkbox"
                            checked={selectedToRemove.has(idx)}
                            onChange={() => toggleRemoveIndex(idx)}
                            onClick={(e) => e.stopPropagation()}
                            className="mt-1 rounded border-zinc-600"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-xs font-medium text-zinc-400">Entry {idx}</span>
                            <p className="mt-1 text-sm text-zinc-300 whitespace-pre-wrap">
                              {preview || '(empty)'}
                            </p>
                            {reason && (
                              <p className="mt-1.5 text-xs text-amber-200/90 italic">
                                Why: {reason}
                              </p>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <button
                    type="button"
                    onClick={handleRemoveSelected}
                    disabled={removing || selectedToRemove.size === 0}
                    className="mt-2 px-3 py-2 rounded bg-red-900/60 hover:bg-red-800/60 text-red-200 text-sm disabled:opacity-50"
                  >
                    {removing ? 'Removing…' : `Remove selected (${selectedToRemove.size})`}
                  </button>
                </>
              )
            })()}
            {scanIndices && scanIndices.length === 0 && !scanLoading && (
              <span className="text-xs text-zinc-500">No irrelevant entries suggested.</span>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
