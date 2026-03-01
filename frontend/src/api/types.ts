// ---------------------------------------------------------------------------
// REST API types
// Mirror the Pydantic models in server/models.py
// Re-exports from types/ for session and WS types.
// ---------------------------------------------------------------------------

export type {
  SessionListItem,
  MessageRecord,
  SessionDetail,
} from './types/sessions'

export type {
  WsConnectionStatus,
  WsClientFrame,
  WsServerFrame,
  ToolCallEvent,
  ApprovalRequest,
  ApprovalOutcome,
  QueuedMessage,
  MessageBlock,
  ChatMessage,
} from './types/ws'

export interface MemoryResponse {
  memory: string
  history: string
}

export interface VerifyBulletResponse {
  verified: boolean
  comment: string
}

export interface ScanIrrelevantHistoryResponse {
  irrelevant_indices: number[]
  reasons?: Record<number, string>
}

export interface MemoryChunkItem {
  id: string
  document: string
  metadata: Record<string, unknown>
}

export interface MemoryChunksListResponse {
  chunks: MemoryChunkItem[]
  total: number
}

// ---------------------------------------------------------------------------
// Knowledge base (KG triples + RAG chunks)
// ---------------------------------------------------------------------------

export interface TripleItem {
  id: number
  subject: string
  predicate: string
  object: string
  created_at: string
}

export interface TriplesListResponse {
  triples: TripleItem[]
  total: number
}

export interface TriplesStatsResponse {
  total: number
  by_predicate: Record<string, number>
}

export interface RagChunkItemKnowledge {
  id: string
  document: string
  metadata: Record<string, unknown>
}

export interface RagChunksListResponseKnowledge {
  chunks: RagChunkItemKnowledge[]
  total: number
}

export interface RagSourcesResponse {
  sources: string[]
}

export interface StatusResponse {
  version: string
  model: string
  workspace: string
  channels_enabled: string[]
}

export interface ChannelStatusItem {
  name: string
  enabled: boolean
  running: boolean
}

export interface ChannelsResponse {
  channels: ChannelStatusItem[]
}

// ---------------------------------------------------------------------------
// Config types
// ---------------------------------------------------------------------------

export interface ModelOption {
  id: string
  label: string
  provider: string
}

export interface ModelsResponse {
  models: ModelOption[]
  current: string
}

export interface ProviderItem {
  id: string
  display_name: string
  has_api_key: boolean
}

export interface ProvidersResponse {
  providers: ProviderItem[]
}

export interface AgentConfigResponse {
  model: string
  max_tokens: number
  temperature: number
  max_tool_iterations: number
  memory_window: number
  workspace: string
  /** low / medium / high for thinking mode; null when off. */
  reasoning_effort?: string | null
  /** Provider name or 'auto' for auto-detection from model. */
  provider?: string
}

export interface ToolsConfigResponse {
  restrict_to_workspace: boolean
  exec_timeout: number
  web_search_api_key_set: boolean
  tool_policy: Record<string, string>
  /** Per-MCP-server guidance (server name → markdown). Injected into agent system prompt. */
  mcp_guidance?: Record<string, string>
  /** When true, desktop tools and Groq-validated run_python (pyautogui-only) are auto-approved. */
  cua_auto_approve?: boolean
  /** Model for CUA run_python safety check (e.g. llama-3.1-8b-instant). */
  cua_safety_model?: string
  /** PATH suffix for shell/exec subprocess (e.g. /opt/bin). */
  path_append?: string
}

export interface MCPServerConfigResponse {
  command: string
  args: string[]
  env: Record<string, string>
  url: string
}

export interface ProviderConfigResponse {
  api_key_set: boolean
  api_base: string | null
}

export interface KgDedupConfigResponse {
  enabled: boolean
  schedule: string
  /** LLM for merge decisions; if empty, uses memory model. */
  kg_dedup_model: string
  llm_batch_size: number
  batch_size: number
}

export interface ConfigResponse {
  agent: AgentConfigResponse
  tools: ToolsConfigResponse
  kg_dedup?: KgDedupConfigResponse
  mcp_servers: Record<string, MCPServerConfigResponse>
  providers: Record<string, ProviderConfigResponse>
  workspace: string
  version: string
}

/** Response from POST /api/llm/profiler (test connection and stream metrics). */
export interface LlmProfilerResult {
  ok: boolean
  error: string | null
  time_to_first_token_ms: number | null
  tokens_per_second: number | null
  has_thinking_stream: boolean
}

export interface AgentConfigPatch {
  model?: string
  max_tokens?: number
  temperature?: number
  max_tool_iterations?: number
  memory_window?: number
  workspace?: string
  reasoning_effort?: string | null
  provider?: string
}

export interface MCPServerPatch {
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
}

export interface ProviderConfigPatch {
  api_key?: string
  api_base?: string | null
}

export interface KgDedupConfigPatch {
  enabled?: boolean
  schedule?: string
  kg_dedup_model?: string
  llm_batch_size?: number
  batch_size?: number
}

export interface ConfigPatch {
  agent?: AgentConfigPatch
  providers?: Record<string, ProviderConfigPatch>
  kg_dedup?: KgDedupConfigPatch
  restrict_to_workspace?: boolean
  exec_timeout?: number
  web_search_api_key?: string
  mcp_servers?: Record<string, MCPServerPatch | null>
  /** Per-MCP-server guidance (server name → markdown). Replaces existing when provided. */
  mcp_guidance?: Record<string, string>
  tool_policy?: Record<string, string>
  /** When true, desktop tools and safe run_python (Groq-validated) are auto-approved. */
  cua_auto_approve?: boolean
  cua_safety_model?: string
  /** PATH suffix for shell/exec subprocess (e.g. /opt/bin). */
  exec_path_append?: string
}

export interface AllowlistEntry {
  tool: string
  pattern: string
}

export interface AllowlistResponse {
  entries: AllowlistEntry[]
}

// ---------------------------------------------------------------------------
// Cron / scheduled jobs
// ---------------------------------------------------------------------------

export interface CronScheduleSummary {
  kind: string
  summary: string
}

export interface CronJobStateResponse {
  next_run_at_ms: number | null
  last_run_at_ms: number | null
  last_status: string | null
  last_error: string | null
}

export interface CronJobItem {
  id: string
  name: string
  enabled: boolean
  schedule: CronScheduleSummary
  state: CronJobStateResponse
  message: string
  is_system_job?: boolean
}

// ---------------------------------------------------------------------------
// KG dedup (Admin)
// ---------------------------------------------------------------------------

export interface KgDedupRunResponse {
  run_id: string
  status: string
}

export interface KgDedupProgressEvent {
  phase?: string
  step?: number
  total?: number
  message?: string
  done?: boolean
  run_id?: string
  stats?: KgDedupStats
  error?: string
  heartbeat?: boolean
}

export interface KgDedupStats {
  nodes_before: number
  nodes_after: number
  triples_before: number
  triples_after: number
  clusters_merged: number
  removed_triples_count: number
  bloat_saved_pct: number
  runtime_sec: number
}

export interface KgDedupAuditListItem {
  run_id: string
  started_at_iso: string | null
  finished_at_iso: string | null
  stats: KgDedupStats
}

/** One removed triple; merged_into is the canonical triple it was merged into (for auditing). */
export interface KgDedupRemovedTriple {
  subject: string
  predicate: string
  object: string
  merged_into?: { subject: string; predicate: string; object: string }
}

export interface KgDedupAuditDetail {
  run_id: string
  started_at_iso: string
  finished_at_iso: string
  stats: KgDedupStats
  merged_nodes: Array<{ old_label: string; canonical_label: string; role: string }>
  removed_triples: KgDedupRemovedTriple[]
}
