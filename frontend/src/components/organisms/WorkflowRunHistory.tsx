import { ChevronDown, Loader2 } from 'lucide-react'
import { StatusBadge } from '../atoms/StatusBadge'
import { formatTimestamp } from '../atoms/Timestamp'
import { WorkflowRunDetail } from './WorkflowRunDetail'
import type { WorkflowRun } from '../../api/workflows'

export type RunsViewFilter = 'workflow' | 'all'

interface WorkflowRunHistoryProps {
  runsView: RunsViewFilter
  onViewChange: (view: RunsViewFilter) => void
  /** Runs for current workflow (when runsView === 'workflow') */
  runs: WorkflowRun[]
  /** All runs (when runsView === 'all') */
  allRuns: WorkflowRun[]
  allRunsLoading: boolean
  selectedRunId: string | null
  runDetail: WorkflowRun | null
  hasMoreRuns: boolean
  runsLoadingMore: boolean
  onSelectRun: (runId: string | null) => void
  onLoadMore: () => void
}

export function WorkflowRunHistory({
  runsView,
  onViewChange,
  runs,
  allRuns,
  allRunsLoading,
  selectedRunId,
  runDetail,
  hasMoreRuns,
  runsLoadingMore,
  onSelectRun,
  onLoadMore,
}: WorkflowRunHistoryProps) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-zinc-400">Run history</h3>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => onViewChange('workflow')}
            className={`rounded px-2 py-0.5 text-[10px] font-medium ${
              runsView === 'workflow' ? 'bg-zinc-600 text-zinc-200' : 'text-zinc-500 hover:bg-zinc-800'
            }`}
          >
            This workflow
          </button>
          <button
            type="button"
            onClick={() => onViewChange('all')}
            className={`rounded px-2 py-0.5 text-[10px] font-medium ${
              runsView === 'all' ? 'bg-zinc-600 text-zinc-200' : 'text-zinc-500 hover:bg-zinc-800'
            }`}
          >
            All runs
          </button>
        </div>
      </div>
      {runsView === 'all' ? (
        allRunsLoading ? (
          <p className="text-xs text-zinc-500 flex items-center gap-1">
            <Loader2 size={12} className="animate-spin" /> Loading…
          </p>
        ) : allRuns.length === 0 ? (
          <p className="text-xs text-zinc-500">No runs yet.</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {allRuns.map((r) => (
              <li key={String(r.run_id)}>
                <button
                  type="button"
                  onClick={() => onSelectRun(selectedRunId === r.run_id ? null : r.run_id)}
                  className="w-full flex items-center justify-between gap-2 rounded px-2 py-1.5 text-left hover:bg-zinc-800/80 transition-colors"
                >
                  <span className="text-zinc-500 truncate max-w-[8rem]" title={r.workflow_name}>
                    {r.workflow_name}
                  </span>
                  <span className="font-mono text-zinc-500 truncate w-16">
                    {String(r.run_id).slice(0, 8)}…
                  </span>
                  <span className="flex items-center gap-1.5 shrink-0">
                    <StatusBadge status={r.status} variant="workflow" />
                    <span className="text-zinc-500">{formatTimestamp(r.started_at_ms)}</span>
                    <ChevronDown
                      size={12}
                      className={`text-zinc-500 ${selectedRunId === r.run_id ? 'rotate-180' : ''}`}
                    />
                  </span>
                </button>
                {selectedRunId === r.run_id && runDetail?.run_id === r.run_id && (
                  <div className="mt-2 ml-2 pl-3 border-l border-zinc-700 space-y-2">
                    <WorkflowRunDetail run={runDetail} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )
      ) : runs.length === 0 ? (
        <p className="text-xs text-zinc-500">No runs yet.</p>
      ) : (
        <>
          <ul className="space-y-1 text-xs">
            {runs.map((r) => (
              <li key={String(r.run_id)}>
                <button
                  type="button"
                  onClick={() => onSelectRun(selectedRunId === r.run_id ? null : r.run_id)}
                  className="w-full flex items-center justify-between gap-2 rounded px-2 py-1.5 text-left hover:bg-zinc-800/80 transition-colors"
                >
                  <span className="font-mono text-zinc-500 truncate">
                    {String(r.run_id).slice(0, 8)}…
                  </span>
                  <span className="flex items-center gap-1.5 shrink-0">
                    <StatusBadge status={r.status} variant="workflow" />
                    <span className="text-zinc-500">{formatTimestamp(r.started_at_ms)}</span>
                    {r.finished_at_ms != null && (
                      <span className="text-zinc-600">
                        ({(r.finished_at_ms - r.started_at_ms) / 1000}s)
                      </span>
                    )}
                    <ChevronDown
                      size={12}
                      className={`text-zinc-500 transition-transform ${
                        selectedRunId === r.run_id ? 'rotate-180' : ''
                      }`}
                    />
                  </span>
                </button>
                {selectedRunId === r.run_id && runDetail?.run_id === r.run_id && (
                  <div className="mt-2 ml-2 pl-3 border-l border-zinc-700 space-y-2">
                    <WorkflowRunDetail run={runDetail} />
                  </div>
                )}
              </li>
            ))}
          </ul>
          {hasMoreRuns && (
            <button
              type="button"
              onClick={onLoadMore}
              disabled={runsLoadingMore}
              className="mt-2 text-[10px] text-blue-400 hover:underline disabled:opacity-50"
            >
              {runsLoadingMore ? 'Loading…' : 'Load more'}
            </button>
          )}
        </>
      )}
    </div>
  )
}
