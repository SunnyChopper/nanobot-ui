import { Plus } from 'lucide-react'
import { WorkflowListItemRow } from '../molecules/WorkflowListItemRow'
import type { WorkflowListItem } from '../../api/workflows'

interface WorkflowListProps {
  workflows: WorkflowListItem[]
  selectedId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string, e: React.MouseEvent) => void
  onNewWorkflow: () => void
}

export function WorkflowList({
  workflows,
  selectedId,
  onSelect,
  onDelete,
  onNewWorkflow,
}: WorkflowListProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-400">All workflows</h2>
        <button
          type="button"
          onClick={onNewWorkflow}
          className="flex items-center gap-1 rounded-lg bg-zinc-700 px-2 py-1 text-xs text-zinc-200 hover:bg-zinc-600"
        >
          <Plus size={12} /> New workflow
        </button>
      </div>
      {workflows.length === 0 ? (
        <p className="text-sm text-zinc-500">No workflows yet. Create one above.</p>
      ) : (
        <ul className="space-y-1">
          {workflows.map((wf) => (
            <WorkflowListItemRow
              key={wf.id}
              name={wf.name}
              selected={selectedId === wf.id}
              lastRunOutcome={wf.last_run_outcome}
              lastRunAt={wf.last_run_at}
              onSelect={() => onSelect(wf.id)}
              onDelete={(e) => onDelete(wf.id, e)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
