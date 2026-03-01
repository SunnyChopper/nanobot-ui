import { useState } from 'react'
import { ChevronDown, ChevronRight, Wrench, CheckCircle2, Loader2 } from 'lucide-react'
import type { ToolCallEvent } from '../../api/types'
import { getToolDisplayName } from '../../lib/toolLabels'

interface Props {
  toolCall: ToolCallEvent
  /** When true, show spinner if no result yet (live streaming). When false, never show spinner (e.g. loaded from session). */
  inProgress?: boolean
}

export function ToolCallCard({ toolCall, inProgress = false }: Props) {
  const [expanded, setExpanded] = useState(false)
  const hasResult = toolCall.result !== undefined
  const displayName = toolCall.name ? getToolDisplayName(toolCall.name) : 'Tool call'
  const showSpinner = !hasResult && inProgress
  const progress = toolCall.progress

  return (
    <div className="my-1 rounded-lg border border-zinc-700 bg-zinc-800/60 text-xs overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-zinc-700/50 transition-colors"
      >
        {showSpinner ? (
          <Loader2 size={13} className="shrink-0 text-amber-400 animate-spin" />
        ) : (
          <Wrench size={13} className="shrink-0 text-amber-400" />
        )}
        <span className="font-mono font-medium text-zinc-200 flex-1 truncate">
          {displayName}
          {progress != null && progress !== '' && (
            <span className="ml-2 text-zinc-500 font-normal">— {progress}</span>
          )}
        </span>
        {hasResult && (
          <CheckCircle2 size={13} className="shrink-0 text-emerald-400" />
        )}
        {expanded ? (
          <ChevronDown size={13} className="shrink-0 text-zinc-500" />
        ) : (
          <ChevronRight size={13} className="shrink-0 text-zinc-500" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-zinc-700">
          {hasResult || (toolCall.arguments && Object.keys(toolCall.arguments).length > 0) ? (
            <>
              <div className="px-3 py-2">
                <p className="text-zinc-500 mb-1 uppercase tracking-wide text-[10px] font-semibold">
                  Arguments
                </p>
                <pre className="text-zinc-300 font-mono whitespace-pre-wrap break-all leading-relaxed">
                  {JSON.stringify(toolCall.arguments ?? {}, null, 2)}
                </pre>
              </div>

              {hasResult && (
                <div className="px-3 py-2 border-t border-zinc-700">
                  <p className="text-zinc-500 mb-1 uppercase tracking-wide text-[10px] font-semibold">
                    Result
                  </p>
                  <pre className="text-zinc-300 font-mono whitespace-pre-wrap break-all leading-relaxed">
                    {toolCall.result}
                  </pre>
                </div>
              )}
            </>
          ) : (
            <div className="px-3 py-2 text-zinc-500 text-xs italic">
              Execution details were not stored for this session (e.g. loaded from an older session or before tool-call storage was enabled).
            </div>
          )}
        </div>
      )}
    </div>
  )
}
