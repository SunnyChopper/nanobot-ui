import { Database, Loader2 } from 'lucide-react'
import type { KgDedupStats } from '../../api/types'

const phaseRanges: Record<string, [number, number]> = {
  load: [0, 10],
  embed: [10, 40],
  top3: [40, 50],
  llm_batch: [50, 90],
  apply: [90, 100],
}

function progressPct(progress: { phase: string; step: number; total: number } | null): number | null {
  if (!progress?.phase) return null
  const range = phaseRanges[progress.phase]
  if (!range) return 5
  const [lo, hi] = range
  const total = progress.total && progress.total > 0 ? progress.total : 1
  const step = Math.min(progress.step ?? 0, total)
  return Math.round(lo + (step / total) * (hi - lo))
}

interface KgDedupRunPanelProps {
  running: boolean
  progress: { phase: string; step: number; total: number; message: string } | null
  result: { runId: string; stats: KgDedupStats; error?: string } | null
  onRun: () => void
  children?: React.ReactNode
}

export function KgDedupRunPanel({ running, progress, result, onRun, children }: KgDedupRunPanelProps) {
  const pct = progressPct(progress)

  return (
    <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-zinc-200 mb-2">
        <Database size={16} className="text-zinc-400" />
        Knowledge graph deduplication
      </h2>
      <p className="text-xs text-zinc-500 mb-4">
        Merge semantically similar nodes and remove duplicate triples to reduce
        bloat. Uses local embeddings (no API cost). Safe to run on a schedule or
        on demand.
      </p>

      <button
        onClick={onRun}
        disabled={running}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
      >
        {running ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Running…
          </>
        ) : (
          'Run dedup'
        )}
      </button>

      {running && progress && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-zinc-400">
            {progress.message || `Phase: ${progress.phase}`}
          </p>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{
                width: pct != null ? `${Math.min(99, pct)}%` : '5%',
              }}
            />
          </div>
          <p className="text-[10px] text-zinc-500">
            {pct != null ? `${pct}%` : 'Starting…'}
          </p>
        </div>
      )}

      {result && !running && (
        <div className="mt-4 p-4 bg-zinc-800/50 rounded-lg space-y-3">
          {result.error ? (
            <p className="text-sm text-red-400">{result.error}</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-4 text-sm">
                <span className="text-zinc-400">
                  Triples: {result.stats.triples_before} → {result.stats.triples_after}
                </span>
                <span className="text-zinc-400">
                  Nodes: {result.stats.nodes_before} → {result.stats.nodes_after}
                </span>
                <span className="font-medium text-emerald-400">
                  Bloat saved: {result.stats.bloat_saved_pct ?? 0}%
                </span>
                {result.stats.runtime_sec != null && (
                  <span className="text-zinc-500">
                    Runtime: {result.stats.runtime_sec}s
                  </span>
                )}
              </div>
              {children}
            </>
          )}
        </div>
      )}
    </section>
  )
}
