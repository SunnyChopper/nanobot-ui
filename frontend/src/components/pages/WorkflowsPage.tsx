import { useCallback, useEffect, useState } from 'react'
import { Loader2, GitBranch } from 'lucide-react'
import {
  getWorkflows,
  getWorkflow,
  runWorkflow,
  listWorkflowRuns,
  getWorkflowRun,
  createCronJob,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
} from '../../api/client'
import type { WorkflowListItem, WorkflowDefinition, WorkflowRun } from '../../api/workflows'
import { ConfirmModal } from '../molecules/ConfirmModal'
import { RunInputModal } from '../molecules/RunInputModal'
import { WorkflowList } from '../organisms/WorkflowList'
import { WorkflowDetailCard } from '../organisms/WorkflowDetailCard'
import { WorkflowReadOnlyGraph } from '../organisms/WorkflowReadOnlyGraph'
import { WorkflowRunHistory } from '../organisms/WorkflowRunHistory'
import type { RunsViewFilter } from '../organisms/WorkflowRunHistory'
import { WorkflowGraphEditor } from '../organisms/WorkflowGraphEditor'

const RUNS_LIMIT = 10

type WorkflowsPageProps = {
  onOpenScheduleForWorkflow?: (workflowId: string) => void
}

export function WorkflowsPage({ onOpenScheduleForWorkflow }: WorkflowsPageProps = {}) {
  const [list, setList] = useState<WorkflowListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [definition, setDefinition] = useState<WorkflowDefinition | null>(null)
  const [runLoading, setRunLoading] = useState(false)
  const [lastRunId, setLastRunId] = useState<string | null>(null)
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [runDetail, setRunDetail] = useState<WorkflowRun | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create')
  const [editorWorkflowId, setEditorWorkflowId] = useState<string | null>(null)
  const [editorDefinition, setEditorDefinition] = useState<WorkflowDefinition | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [runsView, setRunsView] = useState<RunsViewFilter>('workflow')
  const [allRuns, setAllRuns] = useState<WorkflowRun[]>([])
  const [allRunsLoading, setAllRunsLoading] = useState(false)
  const [runsLoadingMore, setRunsLoadingMore] = useState(false)
  const [hasMoreRuns, setHasMoreRuns] = useState(true)
  const [runInputModalOpen, setRunInputModalOpen] = useState(false)
  const [runInputJson, setRunInputJson] = useState('{}')

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getWorkflows()
      setList(data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  useEffect(() => {
    if (!selectedId) {
      setDefinition(null)
      setRuns([])
      return
    }
    let cancelled = false
    getWorkflow(selectedId).then((def) => {
      if (!cancelled) setDefinition(def)
    })
    listWorkflowRuns({ workflow_id: selectedId, limit: RUNS_LIMIT, offset: 0 }).then((r) => {
      if (!cancelled) {
        setRuns(r)
        setHasMoreRuns(r.length >= RUNS_LIMIT)
      }
    })
    return () => {
      cancelled = true
    }
  }, [selectedId])

  useEffect(() => {
    if (runsView !== 'all') return
    setAllRunsLoading(true)
    listWorkflowRuns({ limit: 50, offset: 0 })
      .then(setAllRuns)
      .finally(() => setAllRunsLoading(false))
  }, [runsView])

  const loadMoreRuns = useCallback(async () => {
    if (!selectedId) return
    setRunsLoadingMore(true)
    try {
      const next = await listWorkflowRuns({
        workflow_id: selectedId,
        limit: RUNS_LIMIT,
        offset: runs.length,
      })
      setRuns((prev) => [...prev, ...next])
      setHasMoreRuns(next.length >= RUNS_LIMIT)
    } finally {
      setRunsLoadingMore(false)
    }
  }, [selectedId, runs.length])

  const handleRun = useCallback(
    async (input?: Record<string, unknown>, force = true) => {
      if (!selectedId) return
      setRunLoading(true)
      setLastRunId(null)
      try {
        const { run_id } = await runWorkflow(selectedId, input, { force })
        setLastRunId(run_id)
        setRunsView('workflow')
        const r = await listWorkflowRuns({ workflow_id: selectedId, limit: RUNS_LIMIT, offset: 0 })
        setRuns(r)
        setHasMoreRuns(r.length >= RUNS_LIMIT)
        setSelectedRunId(run_id)
      } catch (e: unknown) {
        const msg =
          e && typeof e === 'object' && 'detail' in e
            ? String((e as { detail: unknown }).detail)
            : 'Run failed'
        alert(msg)
      } finally {
        setRunLoading(false)
      }
    },
    [selectedId]
  )

  const openRunInputModal = useCallback(() => {
    setRunInputJson('{}')
    setRunInputModalOpen(true)
  }, [])

  const handleRunWithInput = useCallback(() => {
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(runInputJson) as Record<string, unknown>
    } catch {
      alert('Invalid JSON')
      return
    }
    setRunInputModalOpen(false)
    handleRun(parsed)
  }, [runInputJson, handleRun])

  useEffect(() => {
    if (!selectedRunId) {
      setRunDetail(null)
      return
    }
    let cancelled = false
    getWorkflowRun(selectedRunId).then((r) => {
      if (!cancelled) setRunDetail(r)
    })
    return () => {
      cancelled = true
    }
  }, [selectedRunId])

  const openEditor = useCallback(
    (mode: 'create' | 'edit') => {
      setEditorMode(mode)
      setEditorWorkflowId(mode === 'edit' ? selectedId : null)
      setEditorDefinition(mode === 'edit' && definition ? definition : null)
      setEditorOpen(true)
    },
    [selectedId, definition]
  )

  const closeEditor = useCallback(() => {
    setEditorOpen(false)
    setEditorWorkflowId(null)
    setEditorDefinition(null)
  }, [])

  const handleEditorSave = useCallback(
    async (def: WorkflowDefinition) => {
      if (editorMode === 'create') {
        def.id = def.id || `workflow-${Date.now()}`
        const created = await createWorkflow({
          id: def.id,
          name: def.name,
          description: def.description,
          status: def.status,
          nodes: def.nodes,
          edges: def.edges,
        })
        await fetchList()
        setSelectedId(created.id)
        setDefinition(created)
        closeEditor()
      } else if (editorWorkflowId) {
        const updated = await updateWorkflow(editorWorkflowId, {
          name: def.name,
          description: def.description,
          status: def.status,
          nodes: def.nodes,
          edges: def.edges,
        })
        setDefinition(updated)
        await fetchList()
        closeEditor()
      }
    },
    [editorMode, editorWorkflowId, fetchList, closeEditor]
  )

  const handleDeleteWorkflow = useCallback(
    async (workflowId: string) => {
      setDeleting(true)
      try {
        await deleteWorkflow(workflowId)
        if (selectedId === workflowId) {
          setSelectedId(null)
          setDefinition(null)
          setRuns([])
          setSelectedRunId(null)
          setRunDetail(null)
        }
        setDeleteConfirmId(null)
        await fetchList()
      } catch (e: unknown) {
        const msg =
          e && typeof e === 'object' && 'message' in e
            ? String((e as { message: unknown }).message)
            : 'Delete failed'
        alert(msg)
      } finally {
        setDeleting(false)
      }
    },
    [selectedId, fetchList]
  )

  const handleSchedule = useCallback(() => {
    if (!selectedId) return
    if (onOpenScheduleForWorkflow) {
      onOpenScheduleForWorkflow(selectedId)
      return
    }
    const name = `workflow:${selectedId}`
    createCronJob({
      name,
      message: '{}',
      task_kind: 'workflow',
      workflow_id: selectedId,
      workflow_input: {},
      schedule_kind: 'cron',
      cron_expr: '0 9 * * *',
    })
      .then(() => alert('Scheduled. Open Scheduled tasks to edit or run now.'))
      .catch((e: unknown) => {
        const msg =
          e && typeof e === 'object' && 'detail' in e
            ? String((e as { detail: unknown }).detail)
            : 'Failed'
        alert(msg)
      })
  }, [selectedId, onOpenScheduleForWorkflow])

  if (editorOpen) {
    return (
      <div className="flex flex-1 flex-col min-h-0 overflow-hidden">
        <WorkflowGraphEditor
          definition={editorDefinition}
          mode={editorMode}
          workflowId={editorWorkflowId}
          onSave={handleEditorSave}
          onCancel={closeEditor}
        />
      </div>
    )
  }

  const deleteWorkflowName =
    deleteConfirmId && list.find((w) => w.id === deleteConfirmId)?.name

  return (
    <div className="flex flex-1 flex-col min-h-0 p-4 overflow-auto">
      <div className="max-w-4xl mx-auto w-full space-y-6">
        <h1 className="text-lg font-semibold text-zinc-200">Workflows</h1>

        {loading ? (
          <div className="flex items-center gap-2 text-zinc-500">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <WorkflowList
              workflows={list}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onDelete={(id, e) => {
                e.stopPropagation()
                setDeleteConfirmId(id)
              }}
              onNewWorkflow={() => openEditor('create')}
            />

            <div className="space-y-4">
              {selectedId && definition && (
                <>
                  <WorkflowDetailCard
                    name={definition.name}
                    description={definition.description}
                    runLoading={runLoading}
                    lastRunId={lastRunId}
                    onRun={() => handleRun()}
                    onRunWithInput={openRunInputModal}
                    onSchedule={handleSchedule}
                    onEdit={() => openEditor('edit')}
                    onDelete={() => setDeleteConfirmId(selectedId)}
                  />

                  <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
                    <h3 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-1">
                      <GitBranch size={14} /> Graph
                    </h3>
                    <WorkflowReadOnlyGraph
                      definition={definition}
                      highlightNodeId={
                        runDetail?.status === 'error' ? runDetail.error_node : undefined
                      }
                    />
                    <p className="mt-2 text-[10px] text-zinc-600">
                      Dashed purple edges are conditional. Node labels show MCP tools when set.
                    </p>
                  </div>

                  <WorkflowRunHistory
                    runsView={runsView}
                    onViewChange={setRunsView}
                    runs={runs}
                    allRuns={allRuns}
                    allRunsLoading={allRunsLoading}
                    selectedRunId={selectedRunId}
                    runDetail={runDetail}
                    hasMoreRuns={hasMoreRuns}
                    runsLoadingMore={runsLoadingMore}
                    onSelectRun={setSelectedRunId}
                    onLoadMore={loadMoreRuns}
                  />
                </>
              )}
              {selectedId && !definition && (
                <div className="flex items-center gap-2 text-zinc-500">
                  <Loader2 size={14} className="animate-spin" /> Loading…
                </div>
              )}
              {!selectedId && (
                <p className="text-sm text-zinc-500">Select a workflow to view details and run.</p>
              )}
            </div>
          </div>
        )}

        {runInputModalOpen && (
          <RunInputModal
            title="Run with input (JSON)"
            value={runInputJson}
            onChange={setRunInputJson}
            onConfirm={handleRunWithInput}
            onCancel={() => setRunInputModalOpen(false)}
          />
        )}

        {deleteConfirmId && (
          <ConfirmModal
            title="Delete workflow?"
            message={`Delete "${deleteWorkflowName ?? deleteConfirmId}"? This cannot be undone.`}
            confirmLabel="Delete"
            variant="danger"
            loading={deleting}
            onConfirm={() => handleDeleteWorkflow(deleteConfirmId)}
            onCancel={() => setDeleteConfirmId(null)}
          />
        )}
      </div>
    </div>
  )
}
