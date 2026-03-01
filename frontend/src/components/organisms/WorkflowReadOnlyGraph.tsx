import { useCallback, useMemo, useRef } from 'react'
import ForceGraph2D, {
  type ForceGraphMethods,
  type LinkObject,
  type NodeObject,
} from 'react-force-graph-2d'
import type { WorkflowDefinition } from '../../api/workflows'

type GraphNode = { id: string; name: string; mcp_tools?: string[] }
type GraphLink = { source: string; target: string; condition?: string }

const PREVIEW_HEIGHT = 320
const FIT_PADDING = 48

interface WorkflowReadOnlyGraphProps {
  definition: WorkflowDefinition
  highlightNodeId?: string | null
}

export function WorkflowReadOnlyGraph({ definition, highlightNodeId }: WorkflowReadOnlyGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<
    ForceGraphMethods<NodeObject<GraphNode>, LinkObject<GraphNode, GraphLink>>
  >(undefined)

  const graphData = useMemo(() => {
    const nodes: GraphNode[] = (definition.nodes ?? []).map((n) => ({
      id: n.id,
      name: n.name || n.id,
      mcp_tools: n.mcp_tools,
    }))
    const hasEnd = (definition.edges ?? []).some((e) => e.to === '__end__' || e.to === 'END')
    if (hasEnd) {
      nodes.push({ id: '__end__', name: 'End' })
    }
    const links: GraphLink[] = (definition.edges ?? []).map((e) => ({
      source: e.from,
      target: e.to === '__end__' || e.to === 'END' ? '__end__' : e.to,
      condition: e.condition,
    }))
    return { nodes, links }
  }, [definition.nodes, definition.edges])

  const handleEngineStop = useCallback(() => {
    graphRef.current?.zoomToFit(0, FIT_PADDING)
  }, [])

  if (graphData.nodes.length === 0) {
    return <p className="text-xs text-zinc-500 py-4">No nodes in this workflow.</p>
  }

  return (
    <div
      ref={containerRef}
      className="w-full min-w-0 rounded-lg bg-zinc-900/80 border border-zinc-700 overflow-hidden"
      style={{ height: PREVIEW_HEIGHT }}
    >
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        height={PREVIEW_HEIGHT}
        nodeId="id"
        linkSource="source"
        linkTarget="target"
        minZoom={0.3}
        maxZoom={2}
        cooldownTicks={100}
        onEngineStop={handleEngineStop}
        nodeLabel={(n) => {
          const node = n as GraphNode
          const tools = node.mcp_tools?.length ? ` (${node.mcp_tools.join(', ')})` : ''
          return `${node.name}${tools}`
        }}
        nodeCanvasObjectMode="after"
        nodeCanvasObject={(node, ctx, globalScale) => {
          const n = node as GraphNode & { x?: number; y?: number }
          const x = n.x ?? 0
          const y = n.y ?? 0
          const isHighlight = highlightNodeId && n.id === highlightNodeId
          if (isHighlight) {
            ctx.beginPath()
            ctx.arc(x, y, 18, 0, 2 * Math.PI)
            ctx.strokeStyle = '#dc2626'
            ctx.lineWidth = 2
            ctx.stroke()
          }
          const label =
            n.name + (n.mcp_tools?.length ? ` [${n.mcp_tools.join(', ')}]` : '')
          const fontSize = Math.min(12 / Math.min(globalScale, 2), 11)
          ctx.font = `${fontSize}px sans-serif`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'middle'
          ctx.fillStyle = isHighlight
            ? '#fca5a5'
            : n.id === '__end__'
              ? '#71717a'
              : '#e4e4e7'
          ctx.fillText(label, x, y + 10)
        }}
        nodeColor={(n) => {
          const id = (n as GraphNode).id
          if (highlightNodeId && id === highlightNodeId) return '#b91c1c'
          return id === '__end__' ? '#52525b' : '#3f3f46'
        }}
        nodeVal={(n) => ((n as GraphNode).id === '__end__' ? 8 : 14)}
        linkColor={(l) => ((l as GraphLink).condition ? '#a78bfa' : '#71717a')}
        linkLineDash={(l) => ((l as GraphLink).condition ? [4, 4] : null)}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        backgroundColor="#18181b"
        enableZoomInteraction={true}
        enablePanInteraction={true}
      />
    </div>
  )
}
