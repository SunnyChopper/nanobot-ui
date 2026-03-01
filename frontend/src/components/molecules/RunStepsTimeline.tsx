import { useState } from 'react'
import type { WorkflowRunStep } from '../../api/workflows'

interface RunStepsTimelineProps {
  steps: WorkflowRunStep[]
}

export function RunStepsTimeline({ steps }: RunStepsTimelineProps) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})
  return (
    <div className="space-y-1">
      <span className="text-zinc-500 font-medium">Step timeline</span>
      <ol className="list-decimal list-inside space-y-2 pl-0">
        {steps.map((step, i) => (
          <li key={i} className="text-zinc-400">
            <button
              type="button"
              onClick={() => setExpanded((e) => ({ ...e, [i]: !e[i] }))}
              className="text-left w-full rounded px-2 py-1 hover:bg-zinc-800/80"
            >
              <span className="font-mono text-zinc-500">{step.node_id}</span>
              <span className="text-zinc-600 mx-1">→</span>
              <span
                className="text-zinc-400 truncate max-w-[12rem] inline-block align-bottom"
                title={step.output}
              >
                {(step.output || '').slice(0, 60)}
                {(step.output?.length ?? 0) > 60 ? '…' : ''}
              </span>
            </button>
            {expanded[i] && (
              <pre className="mt-0.5 ml-4 p-2 rounded bg-zinc-800/80 text-[10px] text-zinc-500 overflow-x-auto whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
                {step.output || '—'}
              </pre>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
