import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { LLMNodeData } from './utils'

function LLMNodeComponent({ data, isConnectable }: NodeProps) {
  const d = data as LLMNodeData
  const promptPreview = (d.prompt || '').slice(0, 60) + ((d.prompt?.length ?? 0) > 60 ? '…' : '')
  const tools = (d.mcp_tools ?? []).join(', ') || '—'

  return (
    <div className="rounded-lg border border-zinc-600 bg-zinc-800/95 shadow-lg min-w-[180px] max-w-[240px]">
      <Handle type="target" position={Position.Left} isConnectable={isConnectable} className="!w-2 !h-2 !bg-zinc-500 !border-zinc-400" />
      <div className="px-3 py-2 space-y-1">
        <div className="font-medium text-zinc-200 text-sm truncate" title={d.name}>
          {d.name || d.id}
        </div>
        {promptPreview && (
          <div className="text-[11px] text-zinc-500 line-clamp-2" title={d.prompt}>
            {promptPreview}
          </div>
        )}
        <div className="text-[10px] text-zinc-600">
          MCP: {tools}
        </div>
      </div>
      <Handle type="source" position={Position.Right} isConnectable={isConnectable} className="!w-2 !h-2 !bg-zinc-500 !border-zinc-400" />
    </div>
  )
}

export const LLMNode = memo(LLMNodeComponent)
