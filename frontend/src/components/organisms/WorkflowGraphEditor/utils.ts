/**
 * Convert between WorkflowDefinition (API) and React Flow nodes/edges.
 * Preserves node position for round-trip editing.
 */

import type { Node, Edge } from '@xyflow/react'
import type { WorkflowDefinition } from '../../../api/workflows'

export const LLM_NODE_TYPE = 'llm'
export const END_NODE_TYPE = 'end'
export const END_NODE_ID = '__end__'

export interface LLMNodeData extends Record<string, unknown> {
  id: string
  name: string
  type: string
  prompt: string
  mcp_tools: string[]
}

export interface EndNodeData extends Record<string, unknown> {
  id: string
  name: string
}

function nextNodeId(existing: string[]): string {
  let n = 0
  while (existing.includes(`node_${n}`)) n++
  return `node_${n}`
}

/** Convert WorkflowDefinition to React Flow nodes and edges. */
export function definitionToFlow(definition: WorkflowDefinition): {
  nodes: Node[]
  edges: Edge[]
} {
  const nodes: Node[] = []
  const nodeIds = new Set<string>()

  for (const n of definition.nodes ?? []) {
    const id = n.id || nextNodeId([...nodeIds])
    nodeIds.add(id)
    const pos = n.position ?? { x: nodes.length * 220, y: 100 }
    nodes.push({
      id,
      type: LLM_NODE_TYPE,
      position: pos,
      data: {
        id,
        name: n.name ?? id,
        type: n.type ?? 'nanobot',
        prompt: n.prompt ?? '',
        mcp_tools: n.mcp_tools ?? [],
      },
    })
  }

  const hasEnd = (definition.edges ?? []).some(
    (e) => e.to === '__end__' || e.to === 'END'
  )
  if (hasEnd) {
    const lastNode = nodes[nodes.length - 1]
    const endPos = lastNode
      ? { x: lastNode.position.x + 220, y: lastNode.position.y }
      : { x: (definition.nodes?.length ?? 0) * 220, y: 100 }
    nodes.push({
      id: END_NODE_ID,
      type: END_NODE_TYPE,
      position: endPos,
      data: { id: END_NODE_ID, name: 'End' },
    })
  }

  const edges: Edge[] = (definition.edges ?? []).map(
    (e, i) => ({
      id: `e-${e.from}-${e.to}-${i}`,
      source: e.from,
      target: e.to === 'END' ? END_NODE_ID : e.to,
      data: e.condition ? { condition: e.condition } : undefined,
    })
  )

  return { nodes, edges }
}

/** Convert React Flow state back to WorkflowDefinition (for save). */
export function flowToDefinition(
  nodes: Node[],
  edges: Edge[],
  meta: { name: string; description?: string; status?: string }
): WorkflowDefinition {
  const workflowNodes = nodes
    .filter((n) => n.type === LLM_NODE_TYPE && n.id !== END_NODE_ID)
    .map((n) => {
      const d = n.data as LLMNodeData
      return {
        id: d.id,
        name: d.name,
        type: d.type ?? 'nanobot',
        prompt: d.prompt ?? '',
        mcp_tools: d.mcp_tools?.length ? d.mcp_tools : undefined,
        position: n.position,
      }
    })

  const workflowEdges = edges
    .filter((e) => e.source && e.target)
    .map((e) => ({
      from: e.source,
      to: e.target,
      ...(e.data && typeof e.data === 'object' && 'condition' in e.data ? { condition: (e.data as { condition?: string }).condition } : {}),
    }))

  return {
    id: '',
    name: meta.name,
    description: meta.description ?? '',
    status: meta.status ?? 'draft',
    nodes: workflowNodes,
    edges: workflowEdges,
  }
}

/** Create a single new LLM node for the palette drop. */
export function createNewLLMNode(position: { x: number; y: number }): Node {
  const id = `node_${Date.now()}`
  return {
    id,
    type: LLM_NODE_TYPE,
    position,
    data: {
      id,
      name: 'New node',
      type: 'nanobot',
      prompt: '',
      mcp_tools: [],
    },
  }
}

/** Create the End node for the palette drop. */
export function createEndNode(position: { x: number; y: number }): Node {
  return {
    id: END_NODE_ID,
    type: END_NODE_TYPE,
    position,
    data: { id: END_NODE_ID, name: 'End' },
  }
}
