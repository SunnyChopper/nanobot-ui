import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  ReactFlowProvider,
  useReactFlow,
  Panel,
  type Connection,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Loader2, Save, X, MessageSquare, Flag } from 'lucide-react'
import { LLMNode } from './LLMNode'
import { EndNode } from './EndNode'
import {
  LLM_NODE_TYPE,
  END_NODE_TYPE,
  definitionToFlow,
  flowToDefinition,
  createNewLLMNode,
  createEndNode,
  type LLMNodeData,
} from './utils'
import type { WorkflowDefinition } from '../../../api/workflows'

const nodeTypes: NodeTypes = {
  [LLM_NODE_TYPE]: LLMNode,
  [END_NODE_TYPE]: EndNode,
}

const PALETTE_ITEM = 'application/x-workflow-node'

type WorkflowGraphEditorInnerProps = {
  initialDefinition: WorkflowDefinition | null
  initialName: string
  initialDescription: string
  mode: 'create' | 'edit'
  workflowId: string | null
  onSave: (def: WorkflowDefinition) => Promise<void>
  onCancel: () => void
}

function WorkflowGraphEditorInner({
  initialDefinition,
  initialName,
  initialDescription,
  mode,
  workflowId,
  onSave,
  onCancel,
}: WorkflowGraphEditorInnerProps) {
  const { screenToFlowPosition } = useReactFlow()
  const initial = useMemo(() => {
    if (initialDefinition && initialDefinition.nodes?.length) {
      return definitionToFlow(initialDefinition)
    }
    return { nodes: [], edges: [] }
  }, [initialDefinition])

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges)
  const [name, setName] = useState(initialName)
  const [description, setDescription] = useState(initialDescription)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId]
  )

  const updateSelectedNodeData = useCallback(
    (updates: Partial<LLMNodeData>) => {
      if (!selectedNodeId) return
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedNodeId ? { ...n, data: { ...n.data, ...updates } } : n
        )
      )
    },
    [selectedNodeId, setNodes]
  )

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) => addEdge({ ...params, type: 'smoothstep' }, eds)),
    [setEdges]
  )

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const type = e.dataTransfer.getData(PALETTE_ITEM) as 'llm' | 'end' | ''
      if (!type) return
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      if (type === 'llm') {
        setNodes((nds) => nds.concat(createNewLLMNode(position)))
      } else if (type === 'end') {
        const existingEnd = nodes.find((n) => n.id === '__end__')
        if (existingEnd) return
        setNodes((nds) => nds.concat(createEndNode(position)))
      }
    },
    [screenToFlowPosition, setNodes, nodes]
  )

  const handleSave = useCallback(async () => {
    setError(null)
    const def = flowToDefinition(nodes, edges, { name, description, status: 'draft' })
    if (workflowId) def.id = workflowId
    if (!def.nodes.length) {
      setError('Add at least one node.')
      return
    }
    setSaving(true)
    try {
      await onSave(def)
    } catch (e: unknown) {
      const msg =
        e && typeof e === 'object' && 'message' in e
          ? String((e as { message: unknown }).message)
          : 'Save failed'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }, [nodes, edges, name, description, workflowId, onSave])

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2 shrink-0">
        <div className="flex items-center gap-4">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Workflow name"
            className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200 placeholder-zinc-500 w-48"
          />
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-400 placeholder-zinc-500 w-64"
          />
        </div>
        <div className="flex items-center gap-2">
          {error && <span className="text-red-400 text-sm mr-2">{error}</span>}
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-600 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800"
          >
            <X size={14} /> Cancel
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        <div className="w-44 border-r border-zinc-800 p-2 flex flex-col gap-2 shrink-0 bg-zinc-900/50">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium px-1 mb-1">
            Nodes
          </div>
          <div
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData(PALETTE_ITEM, 'llm')
              e.dataTransfer.effectAllowed = 'move'
            }}
            className="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 cursor-grab active:cursor-grabbing text-zinc-300 hover:border-zinc-600 hover:bg-zinc-700/80 transition-colors"
          >
            <MessageSquare size={16} className="shrink-0 text-zinc-400" />
            <span className="text-sm">LLM node</span>
          </div>
          <div
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData(PALETTE_ITEM, 'end')
              e.dataTransfer.effectAllowed = 'move'
            }}
            className="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 cursor-grab active:cursor-grabbing text-zinc-300 hover:border-zinc-600 hover:bg-zinc-700/80 transition-colors"
          >
            <Flag size={16} className="shrink-0 text-zinc-400" />
            <span className="text-sm">End</span>
          </div>
          <p className="text-[10px] text-zinc-600 mt-2 px-1">
            Drag onto canvas to add. Connect from right handle to left handle.
          </p>
        </div>

        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDragOver={onDragOver}
            onDrop={onDrop}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(null)}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={{ type: 'smoothstep' }}
            fitView
            className="bg-zinc-900/30"
            minZoom={0.2}
            maxZoom={1.5}
          >
            <Controls className="!bg-zinc-800 !border-zinc-700 !rounded-lg" />
            <Background gap={16} size={1} color="rgb(63 63 70)" className="bg-zinc-900/50" />
            <Panel position="top-left" className="m-2">
              <span className="text-xs text-zinc-500">
                {mode === 'create' ? 'New workflow' : 'Editing workflow'}
              </span>
            </Panel>
          </ReactFlow>
        </div>

        {selectedNode &&
          selectedNode.type === LLM_NODE_TYPE &&
          (() => {
            const d = selectedNode.data as LLMNodeData
            return (
              <div className="w-72 border-l border-zinc-800 p-3 flex flex-col gap-2 shrink-0 bg-zinc-900/50 overflow-y-auto">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
                  Node properties
                </div>
                <div>
                  <label className="block text-[10px] text-zinc-500 mb-0.5">Name</label>
                  <input
                    value={d.name ?? ''}
                    onChange={(e) => updateSelectedNodeData({ name: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-200"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-zinc-500 mb-0.5">Prompt / instructions</label>
                  <textarea
                    value={d.prompt ?? ''}
                    onChange={(e) => updateSelectedNodeData({ prompt: e.target.value })}
                    rows={4}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-200 resize-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-zinc-500 mb-0.5">MCP tools (comma-separated)</label>
                  <input
                    value={d.mcp_tools?.join(', ') ?? ''}
                    onChange={(e) =>
                      updateSelectedNodeData({
                        mcp_tools: e.target.value
                          .split(',')
                          .map((s) => s.trim())
                          .filter(Boolean),
                      })
                    }
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-200"
                  />
                </div>
              </div>
            )
          })()}
      </div>
    </div>
  )
}

export type WorkflowGraphEditorProps = {
  definition: WorkflowDefinition | null
  mode: 'create' | 'edit'
  workflowId: string | null
  onSave: (def: WorkflowDefinition) => Promise<void>
  onCancel: () => void
}

export function WorkflowGraphEditor({
  definition,
  mode,
  workflowId,
  onSave,
  onCancel,
}: WorkflowGraphEditorProps) {
  const initialName = definition?.name ?? 'New workflow'
  const initialDescription = definition?.description ?? ''

  return (
    <ReactFlowProvider>
      <WorkflowGraphEditorInner
        initialDefinition={definition}
        initialName={initialName}
        initialDescription={initialDescription}
        mode={mode}
        workflowId={workflowId}
        onSave={onSave}
        onCancel={onCancel}
      />
    </ReactFlowProvider>
  )
}
