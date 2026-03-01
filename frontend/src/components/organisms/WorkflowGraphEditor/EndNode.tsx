import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { EndNodeData } from './utils'

function EndNodeComponent({ data, isConnectable }: NodeProps) {
  const d = data as EndNodeData
  return (
    <div className="rounded-full border-2 border-zinc-500 bg-zinc-700/90 px-4 py-2 shadow">
      <Handle type="target" position={Position.Left} isConnectable={isConnectable} className="!w-2 !h-2 !bg-zinc-400 !border-zinc-300" />
      <span className="text-xs font-medium text-zinc-300">{d.name}</span>
    </div>
  )
}

export const EndNode = memo(EndNodeComponent)
