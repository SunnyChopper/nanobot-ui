import { useState } from 'react'
import {
  startKgDedup,
  streamKgDedupProgress,
  getKgDedupAudit,
  restoreKgDedupTriple,
} from '../api/client'
import type { KgDedupProgressEvent, KgDedupStats, KgDedupAuditDetail, KgDedupRemovedTriple } from '../api/types'
import { KgDedupRunPanel } from './organisms/KgDedupRunPanel'
import { KgDedupAuditPanel } from './organisms/KgDedupAuditPanel'

export function AdminPage() {
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState<{
    phase: string
    step: number
    total: number
    message: string
  } | null>(null)
  const [result, setResult] = useState<{
    runId: string
    stats: KgDedupStats
    error?: string
  } | null>(null)
  const [auditOpen, setAuditOpen] = useState(false)
  const [audit, setAudit] = useState<KgDedupAuditDetail | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)

  async function handleRunDedup() {
    setRunning(true)
    setProgress({ phase: 'load', step: 0, total: 1, message: 'Starting…' })
    setResult(null)
    setAudit(null)
    setAuditOpen(false)
    try {
      const { run_id } = await startKgDedup()
      await streamKgDedupProgress(run_id, (event: KgDedupProgressEvent) => {
        if (event.heartbeat) return
        if (event.done) {
          setRunning(false)
          if (event.error) {
            setResult({ runId: run_id, stats: {} as KgDedupStats, error: event.error })
          } else if (event.stats) {
            setResult({ runId: run_id, stats: event.stats })
          }
          setProgress(null)
          return
        }
        setProgress({
          phase: event.phase ?? 'unknown',
          step: event.step ?? 0,
          total: event.total ?? 1,
          message: event.message ?? '',
        })
      })
    } catch (e) {
      setRunning(false)
      setProgress(null)
      setResult({
        runId: '',
        stats: {} as KgDedupStats,
        error: e instanceof Error ? e.message : String(e),
      })
    }
  }

  async function handleViewDeleted() {
    if (!result?.runId) return
    setAuditOpen(true)
    if (audit?.run_id === result.runId) return
    setAuditLoading(true)
    try {
      const data = await getKgDedupAudit(result.runId)
      setAudit(data)
    } catch {
      setAudit(null)
    } finally {
      setAuditLoading(false)
    }
  }

  async function handleRestore(t: KgDedupRemovedTriple) {
    try {
      await restoreKgDedupTriple({ subject: t.subject, predicate: t.predicate, object: t.object })
      if (audit && result?.runId) {
        setAudit({
          ...audit,
          removed_triples: audit.removed_triples.filter(
            (r) =>
              !(r.subject === t.subject && r.predicate === t.predicate && r.object === t.object)
          ),
        })
      }
    } catch {
      // leave list as-is on error
    }
  }

  return (
    <div className="flex flex-col h-full bg-zinc-950 overflow-y-auto">
      <div className="sticky top-0 z-10 bg-zinc-950 border-b border-zinc-800 px-6 py-4">
        <h1 className="text-base font-semibold text-zinc-100">Admin</h1>
        <p className="text-xs text-zinc-500 mt-0.5">
          Maintenance and data management actions.
        </p>
      </div>

      <div className="flex-1 px-6 py-6 max-w-4xl mx-auto w-full space-y-6">
        <KgDedupRunPanel
          running={running}
          progress={progress}
          result={result}
          onRun={handleRunDedup}
        >
          <KgDedupAuditPanel
            open={auditOpen}
            onToggle={() => {
              if (auditOpen) {
                setAuditOpen(false)
              } else {
                handleViewDeleted()
              }
            }}
            audit={audit}
            auditLoading={auditLoading}
            onRestore={handleRestore}
          />
        </KgDedupRunPanel>
      </div>
    </div>
  )
}
