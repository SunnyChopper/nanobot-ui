import { Loader2, Play, Pencil, Trash2 } from 'lucide-react'

interface WorkflowDetailCardProps {
  name: string
  description?: string
  runLoading: boolean
  lastRunId: string | null
  onRun: () => void
  onRunWithInput: () => void
  onSchedule: () => void
  onEdit: () => void
  onDelete: () => void
}

export function WorkflowDetailCard({
  name,
  description,
  runLoading,
  lastRunId,
  onRun,
  onRunWithInput,
  onSchedule,
  onEdit,
  onDelete,
}: WorkflowDetailCardProps) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
      <h2 className="text-sm font-medium text-zinc-300 mb-2">{name}</h2>
      {description && <p className="text-xs text-zinc-500 mb-4">{description}</p>}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onRun}
          disabled={runLoading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-600 disabled:opacity-50"
        >
          {runLoading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          Run now
        </button>
        <button
          type="button"
          onClick={onRunWithInput}
          disabled={runLoading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-600 disabled:opacity-50"
        >
          Run with input
        </button>
        <button
          type="button"
          onClick={onSchedule}
          className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-600"
        >
          Schedule
        </button>
        <button
          type="button"
          onClick={onEdit}
          className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-600"
        >
          <Pencil size={14} /> Edit
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-600 px-3 py-1.5 text-sm text-zinc-400 hover:bg-red-900/20 hover:text-red-400 hover:border-red-800"
        >
          <Trash2 size={14} /> Delete
        </button>
      </div>
      {lastRunId && (
        <p className="mt-2 text-xs text-emerald-400">Run started: {lastRunId}</p>
      )}
    </div>
  )
}
