/** Workflows API */

import { apiFetch } from './http'

export interface WorkflowListItem {
  id: string
  name: string
  description: string
  status: string
  last_run_at: number | null
  last_run_outcome: string | null
}

export interface WorkflowDefinition {
  id: string
  name: string
  description?: string
  status?: string
  nodes: Array<{
    id: string
    name?: string
    type?: string
    prompt?: string
    mcp_tools?: string[]
    position?: { x: number; y: number }
  }>
  edges: Array<{ from: string; to: string; condition?: string }>
}

export interface WorkflowRunErrorDetail {
  stack_trace?: string
  node_input_snapshot?: Record<string, unknown>
}

export interface WorkflowRunStep {
  node_id: string
  node_name: string
  output: string
}

export interface WorkflowRun {
  run_id: string
  workflow_name: string
  status: string
  started_at_ms: number
  finished_at_ms?: number
  input_snapshot?: Record<string, unknown>
  result_envelope?: {
    steps?: WorkflowRunStep[]
    last_output?: string
    input?: Record<string, unknown>
    [key: string]: unknown
  }
  error_message?: string
  error_node?: string
  error_detail?: WorkflowRunErrorDetail
  langsmith_run_id?: string
}

export function getWorkflows(): Promise<WorkflowListItem[]> {
  return apiFetch('/workflows')
}

export function getWorkflow(workflowId: string): Promise<WorkflowDefinition> {
  return apiFetch(`/workflows/${encodeURIComponent(workflowId)}`)
}

export function createWorkflow(body: {
  id?: string
  name: string
  description?: string
  status?: string
  nodes?: WorkflowDefinition['nodes']
  edges?: WorkflowDefinition['edges']
}): Promise<WorkflowDefinition> {
  return apiFetch('/workflows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function updateWorkflow(
  workflowId: string,
  body: Partial<WorkflowDefinition>
): Promise<WorkflowDefinition> {
  return apiFetch(`/workflows/${encodeURIComponent(workflowId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function deleteWorkflow(workflowId: string): Promise<void> {
  return apiFetch(`/workflows/${encodeURIComponent(workflowId)}`, {
    method: 'DELETE',
  })
}

export function runWorkflow(
  workflowId: string,
  input?: Record<string, unknown>,
  options?: { force?: boolean }
): Promise<{ run_id: string }> {
  const body: { input?: Record<string, unknown>; force?: boolean } =
    input != null ? { input } : {}
  if (options?.force === true) body.force = true
  return apiFetch(`/workflows/${encodeURIComponent(workflowId)}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function listWorkflowRuns(params?: {
  workflow_id?: string
  limit?: number
  offset?: number
}): Promise<WorkflowRun[]> {
  const sp = new URLSearchParams()
  if (params?.workflow_id) sp.set('workflow_id', params.workflow_id)
  if (params?.limit != null) sp.set('limit', String(params.limit))
  if (params?.offset != null) sp.set('offset', String(params.offset))
  const q = sp.toString()
  return apiFetch(`/workflow-runs${q ? `?${q}` : ''}`)
}

export function getWorkflowRun(runId: string): Promise<WorkflowRun> {
  return apiFetch(`/workflow-runs/${encodeURIComponent(runId)}`)
}
