import { ChevronRight, Trash2 } from 'lucide-react'
import { StatusBadge } from '../atoms/StatusBadge'
import { Timestamp } from '../atoms/Timestamp'

interface WorkflowListItemRowProps {
  name: string
  selected: boolean
  lastRunOutcome: string | null
  lastRunAt: number | null
  onSelect: () => void
  onDelete: (e: React.MouseEvent) => void
}

export function WorkflowListItemRow({
  name,
  selected,
  lastRunOutcome,
  lastRunAt,
  onSelect,
  onDelete,
}: WorkflowListItemRowProps) {
  return (
    <li className="group">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onSelect}
          className={`flex-1 flex items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors ${
            selected ? 'bg-zinc-700 text-zinc-100' : 'hover:bg-zinc-800 text-zinc-300'
          }`}
        >
          <span className="font-medium truncate">{name}</span>
          <ChevronRight size={14} className="shrink-0 text-zinc-500" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="rounded p-1.5 text-zinc-500 hover:text-red-400 hover:bg-zinc-800 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
          title="Delete workflow"
        >
          <Trash2 size={14} />
        </button>
      </div>
      <div className="flex items-center gap-2 pl-3 text-xs text-zinc-500">
        <StatusBadge status={lastRunOutcome} variant="workflow" />
        <Timestamp ms={lastRunAt} />
      </div>
    </li>
  )
}
