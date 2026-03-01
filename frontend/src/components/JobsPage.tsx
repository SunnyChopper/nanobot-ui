import { useEffect, useState } from 'react'
import { Clock, Loader2, Pause, Play, Plus, Trash2 } from 'lucide-react'
import {
  createCronJob,
  deleteCronJob,
  getCronJobs,
  getWorkflows,
  updateCronJobEnabled,
  updateCronJobSchedule,
} from '../api/client'
import type { CronJobItem } from '../api/types'
import type { WorkflowListItem } from '../api/workflows'
import { useChatStore } from '../stores/chatStore'

type JobsPageProps = {
  initialScheduleWorkflowId?: string | null
  onConsumedScheduleWorkflowId?: () => void
}

function formatMs(ms: number | null): string {
  if (ms == null) return '—'
  const d = new Date(ms)
  return d.toLocaleString(undefined, {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

/** Format local datetime for input[type="datetime-local"] (YYYY-MM-DDTHH:mm). */
function toDatetimeLocal(ms: number | null): string {
  if (ms == null) return ''
  const d = new Date(ms)
  const y = d.getFullYear()
  const M = String(d.getMonth() + 1).padStart(2, '0')
  const D = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${M}-${D}T${h}:${m}`
}

/** Parse datetime-local value to ISO string for API. */
function fromDatetimeLocal(value: string): string {
  if (!value) return ''
  const d = new Date(value)
  return d.toISOString()
}

function statusBadge(status: string | null) {
  if (!status) return <span className="text-zinc-500">—</span>
  const cls =
    status === 'ok'
      ? 'bg-emerald-900/50 text-emerald-400'
      : status === 'error'
        ? 'bg-red-900/50 text-red-400'
        : 'bg-zinc-700 text-zinc-400'
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}

type ScheduleKind = 'every' | 'at' | 'cron'
type TaskKind = 'prompt' | 'workflow'

export function JobsPage({
  initialScheduleWorkflowId,
  onConsumedScheduleWorkflowId,
}: JobsPageProps = {}) {
  const loadSessions = useChatStore((s) => s.loadSessions)
  const [jobs, setJobs] = useState<CronJobItem[]>([])
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [taskKind, setTaskKind] = useState<TaskKind>('prompt')
  const [createName, setCreateName] = useState('')
  const [createMessage, setCreateMessage] = useState('')
  const [createWorkflowId, setCreateWorkflowId] = useState('')
  const [createWorkflowInput, setCreateWorkflowInput] = useState('{}')
  const [scheduleKind, setScheduleKind] = useState<ScheduleKind>('every')
  const [createInterval, setCreateInterval] = useState(60)
  const [createRunAt, setCreateRunAt] = useState(toDatetimeLocal(Date.now() + 60 * 60 * 1000))
  const [createDeleteAfterRun, setCreateDeleteAfterRun] = useState(false)
  const [createCronExpr, setCreateCronExpr] = useState('0 9 * * *')
  const [createCronTz, setCreateCronTz] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [editingScheduleId, setEditingScheduleId] = useState<string | null>(null)
  const [editCronExpr, setEditCronExpr] = useState('')
  const [editCronTz, setEditCronTz] = useState('')
  const [savingSchedule, setSavingSchedule] = useState(false)

  const fetchJobs = async () => {
    setLoading(true)
    try {
      const list = await getCronJobs()
      setJobs(list)
    } finally {
      setLoading(false)
    }
  }

  const refreshJobsQuiet = async () => {
    try {
      const list = await getCronJobs()
      setJobs(list)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    fetchJobs()
  }, [])

  useEffect(() => {
    getWorkflows().then(setWorkflows).catch(() => setWorkflows([]))
  }, [])

  useEffect(() => {
    if (initialScheduleWorkflowId && workflows.length > 0) {
      setModalOpen(true)
      setTaskKind('workflow')
      setCreateWorkflowId(initialScheduleWorkflowId)
      setCreateName(`workflow:${initialScheduleWorkflowId}`)
      setCreateMessage('{}')
      setCreateWorkflowInput('{}')
      onConsumedScheduleWorkflowId?.()
    }
  }, [initialScheduleWorkflowId, workflows.length])

  // Refresh thread list and jobs periodically so new cron-run threads and last/next run times update
  useEffect(() => {
    const t = setInterval(() => {
      loadSessions()
      refreshJobsQuiet()
    }, 10000)
    return () => clearInterval(t)
  }, [loadSessions])

  const handleToggle = async (job: CronJobItem) => {
    setTogglingId(job.id)
    try {
      const updated = await updateCronJobEnabled(job.id, !job.enabled)
      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)))
    } finally {
      setTogglingId(null)
    }
  }

  const handleDelete = async (job: CronJobItem) => {
    if (job.is_system_job) return
    if (!window.confirm(`Delete scheduled task "${job.name}"?`)) return
    setDeletingId(job.id)
    try {
      await deleteCronJob(job.id)
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
    } catch (err) {
      // 403 for system events
      await fetchJobs()
    } finally {
      setDeletingId(null)
    }
  }

  const startEditSchedule = (job: CronJobItem) => {
    setEditingScheduleId(job.id)
    const summary = job.schedule.summary || ''
    const inParen = summary.indexOf(' (')
    const expr = inParen >= 0 ? summary.slice(0, inParen).trim() : summary.trim()
    const tz = inParen >= 0 ? summary.slice(inParen + 2).replace(/\)$/, '').trim() : ''
    setEditCronExpr(expr || '0 3 * * *')
    setEditCronTz(tz)
  }

  const handleSaveSchedule = async (jobId: string) => {
    setSavingSchedule(true)
    try {
      const updated = await updateCronJobSchedule(jobId, {
        schedule_kind: 'cron',
        cron_expr: editCronExpr.trim() || '0 3 * * *',
        cron_tz: editCronTz.trim() || null,
      })
      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)))
      setEditingScheduleId(null)
    } finally {
      setSavingSchedule(false)
    }
  }

  async function handleCreateJob(e: React.FormEvent) {
    e.preventDefault()
    const name =
      taskKind === 'workflow' && createWorkflowId
        ? `workflow:${createWorkflowId}`
        : createName.trim()
    const message = taskKind === 'prompt' ? createMessage.trim() : '{}'
    if (!name) return
    if (taskKind === 'prompt' && !message) return
    if (taskKind === 'workflow' && !createWorkflowId) {
      setCreateError('Select a workflow')
      return
    }

    let workflowInput: Record<string, unknown> | null = null
    if (taskKind === 'workflow' && createWorkflowInput.trim()) {
      try {
        workflowInput = JSON.parse(createWorkflowInput.trim()) as Record<string, unknown>
      } catch {
        setCreateError('Workflow input must be valid JSON')
        return
      }
    }

    if (scheduleKind === 'cron' && !createCronExpr.trim()) {
      setCreateError('Cron expression is required')
      return
    }
    if (scheduleKind === 'at' && !createRunAt.trim()) {
      setCreateError('Run at date/time is required')
      return
    }

    setCreating(true)
    setCreateError(null)
    try {
      await createCronJob({
        name,
        message: taskKind === 'workflow' ? JSON.stringify(workflowInput || {}) : message,
        task_kind: taskKind,
        workflow_id: taskKind === 'workflow' ? createWorkflowId : null,
        workflow_input: workflowInput ?? undefined,
        schedule_kind: scheduleKind,
        interval_minutes: Math.max(1, createInterval),
        run_at_iso: scheduleKind === 'at' ? fromDatetimeLocal(createRunAt) : null,
        delete_after_run: scheduleKind === 'at' ? createDeleteAfterRun : false,
        cron_expr: scheduleKind === 'cron' ? createCronExpr.trim() : null,
        cron_tz: scheduleKind === 'cron' && createCronTz.trim() ? createCronTz.trim() : null,
      })
      await fetchJobs()
      setModalOpen(false)
      setCreateName('')
      setCreateMessage('')
      setTaskKind('prompt')
      setCreateWorkflowId('')
      setCreateWorkflowInput('{}')
      setScheduleKind('every')
      setCreateInterval(60)
      setCreateRunAt(toDatetimeLocal(Date.now() + 60 * 60 * 1000))
      setCreateDeleteAfterRun(false)
      setCreateCronExpr('0 9 * * *')
      setCreateCronTz('')
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create job')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h1 className="flex items-center gap-2 text-lg font-semibold text-zinc-200">
              <Clock size={20} />
              Scheduled tasks
            </h1>
            <p className="mt-1 text-sm text-zinc-500">
              View and enable/disable cron jobs, or create a new one.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm"
          >
            <Plus size={16} />
            New job
          </button>
        </div>
      </div>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          onClick={() => setModalOpen(false)}
          onKeyDown={(e) => e.key === 'Escape' && setModalOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-zinc-800">
              <h2 className="text-lg font-semibold text-zinc-200">Create scheduled task</h2>
              <p className="text-sm text-zinc-500 mt-0.5">
                Run a prompt (agent message) or a named workflow on a schedule.
              </p>
            </div>
            <form onSubmit={handleCreateJob} className="p-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-2">Task type</label>
                <div className="flex flex-wrap gap-2">
                  {(['prompt', 'workflow'] as const).map((k) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setTaskKind(k)}
                      className={`px-3 py-1.5 rounded-lg text-sm ${
                        taskKind === k
                          ? 'bg-blue-600 text-white'
                          : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                      }`}
                    >
                      {k === 'prompt' ? 'Prompt (agent message)' : 'Workflow'}
                    </button>
                  ))}
                </div>
              </div>

              {taskKind === 'prompt' && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Name</label>
                    <input
                      type="text"
                      value={createName}
                      onChange={(e) => setCreateName(e.target.value)}
                      placeholder="e.g. Daily standup"
                      className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Message (prompt for the agent)</label>
                    <textarea
                      value={createMessage}
                      onChange={(e) => setCreateMessage(e.target.value)}
                      placeholder="e.g. Summarize my open PRs and remind me of blockers"
                      rows={3}
                      className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-500 resize-none"
                      required
                    />
                  </div>
                </>
              )}

              {taskKind === 'workflow' && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Workflow</label>
                    <select
                      value={createWorkflowId}
                      onChange={(e) => {
                        const id = e.target.value
                        setCreateWorkflowId(id)
                        setCreateName(id ? `workflow:${id}` : '')
                      }}
                      className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 outline-none focus:border-zinc-500"
                      required
                    >
                      <option value="">Select a workflow</option>
                      {workflows.map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name} ({w.id})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Input (optional JSON)</label>
                    <textarea
                      value={createWorkflowInput}
                      onChange={(e) => setCreateWorkflowInput(e.target.value)}
                      placeholder='{"key": "value"}'
                      rows={2}
                      className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm font-mono text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-500 resize-none"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-2">Schedule</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {(['every', 'at', 'cron'] as const).map((k) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setScheduleKind(k)}
                      className={`px-3 py-1.5 rounded-lg text-sm ${
                        scheduleKind === k
                          ? 'bg-blue-600 text-white'
                          : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                      }`}
                    >
                      {k === 'every' ? 'Recurring (interval)' : k === 'at' ? 'Run once at' : 'Cron expression'}
                    </button>
                  ))}
                </div>

                {scheduleKind === 'every' && (
                  <div>
                    <label className="block text-xs text-zinc-500 mb-1">Run every (minutes)</label>
                    <input
                      type="number"
                      min={1}
                      value={createInterval}
                      onChange={(e) => setCreateInterval(parseInt(e.target.value, 10) || 60)}
                      className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 outline-none focus:border-zinc-500"
                    />
                  </div>
                )}

                {scheduleKind === 'at' && (
                  <div className="space-y-2">
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">Date and time (local)</label>
                      <input
                        type="datetime-local"
                        value={createRunAt}
                        onChange={(e) => setCreateRunAt(e.target.value)}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 outline-none focus:border-zinc-500"
                      />
                    </div>
                    <label className="flex items-center gap-2 text-sm text-zinc-400">
                      <input
                        type="checkbox"
                        checked={createDeleteAfterRun}
                        onChange={(e) => setCreateDeleteAfterRun(e.target.checked)}
                        className="rounded border-zinc-600 bg-zinc-800"
                      />
                      Remove job after it runs once
                    </label>
                  </div>
                )}

                {scheduleKind === 'cron' && (
                  <div className="space-y-2">
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">Cron expression</label>
                      <input
                        type="text"
                        value={createCronExpr}
                        onChange={(e) => setCreateCronExpr(e.target.value)}
                        placeholder="0 9 * * *"
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm font-mono text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-500"
                      />
                      <p className="text-xs text-zinc-500 mt-0.5">
                        e.g. 0 9 * * * = daily at 9:00; 0 */2 * * * = every 2 hours
                      </p>
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">Timezone (optional)</label>
                      <input
                        type="text"
                        value={createCronTz}
                        onChange={(e) => setCreateCronTz(e.target.value)}
                        placeholder="e.g. America/New_York"
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 outline-none focus:border-zinc-500"
                      />
                    </div>
                  </div>
                )}
              </div>

              {createError && (
                <p className="text-sm text-red-400">{createError}</p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-800 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50"
                >
                  {creating ? 'Creating…' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="flex-1 p-4 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-zinc-500">
            <Loader2 className="animate-spin size-6" />
          </div>
        ) : jobs.length === 0 ? (
          <p className="text-sm text-zinc-500">No scheduled jobs. Create one or ask the agent to add one.</p>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-zinc-200 truncate">{job.name}</span>
                      <span className="text-xs text-zinc-500 font-mono">{job.id}</span>
                      {!job.enabled && (
                        <span className="text-xs text-zinc-500 italic">(disabled)</span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      {job.schedule.summary}
                      {job.message ? ` · "${job.message.slice(0, 50)}${job.message.length > 50 ? '…' : ''}"` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {job.is_system_job && editingScheduleId !== job.id && (
                      <button
                        type="button"
                        onClick={() => startEditSchedule(job)}
                        className="p-2 rounded-lg border border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors text-xs"
                        title="Edit run time"
                      >
                        Edit schedule
                      </button>
                    )}
                    <button
                      onClick={() => handleToggle(job)}
                      disabled={togglingId === job.id}
                      className="p-2 rounded-lg border border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors disabled:opacity-50"
                      title={job.enabled ? 'Disable' : 'Enable'}
                    >
                      {togglingId === job.id ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : job.enabled ? (
                        <Pause size={16} />
                      ) : (
                        <Play size={16} />
                      )}
                    </button>
                    {!job.is_system_job && (
                      <button
                        onClick={() => handleDelete(job)}
                        disabled={deletingId === job.id}
                        className="p-2 rounded-lg border border-zinc-700 hover:bg-red-900/50 text-zinc-400 hover:text-red-400 transition-colors disabled:opacity-50"
                        title="Delete"
                      >
                        {deletingId === job.id ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Trash2 size={16} />
                        )}
                      </button>
                    )}
                  </div>
                </div>
                {job.is_system_job && editingScheduleId === job.id && (
                  <div className="mt-3 pt-3 border-t border-zinc-700 flex flex-wrap items-center gap-2">
                    <label className="text-xs text-zinc-500">Cron expression</label>
                    <input
                      type="text"
                      value={editCronExpr}
                      onChange={(e) => setEditCronExpr(e.target.value)}
                      placeholder="0 3 * * *"
                      className="flex-1 min-w-[8rem] bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm font-mono text-zinc-200"
                    />
                    <input
                      type="text"
                      value={editCronTz}
                      onChange={(e) => setEditCronTz(e.target.value)}
                      placeholder="Timezone (optional)"
                      className="w-40 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-200"
                    />
                    <button
                      type="button"
                      onClick={() => handleSaveSchedule(job.id)}
                      disabled={savingSchedule}
                      className="px-2 py-1 rounded bg-blue-600 text-white text-xs disabled:opacity-50"
                    >
                      {savingSchedule ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingScheduleId(null)}
                      className="px-2 py-1 rounded border border-zinc-600 text-zinc-400 text-xs"
                    >
                      Cancel
                    </button>
                  </div>
                )}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div>
                    <span className="text-zinc-500">Next run</span>
                    <p className="text-zinc-300 font-mono">{formatMs(job.state.next_run_at_ms)}</p>
                  </div>
                  <div>
                    <span className="text-zinc-500">Last run</span>
                    <p className="text-zinc-300 font-mono">{formatMs(job.state.last_run_at_ms)}</p>
                  </div>
                  <div>
                    <span className="text-zinc-500">Status</span>
                    <p>{statusBadge(job.state.last_status)}</p>
                  </div>
                  {job.state.last_error && (
                    <div className="col-span-2 sm:col-span-4">
                      <span className="text-zinc-500">Last error</span>
                      <p className="text-red-400/90 truncate" title={job.state.last_error}>
                        {job.state.last_error}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
