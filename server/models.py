"""
Pydantic request/response models for the nanobot web API.

These mirror the data stored by nanobot's SessionManager and ChannelManager
so that the TypeScript frontend has a stable, versioned contract.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Session models
# ---------------------------------------------------------------------------


class SessionListItem(BaseModel):
    """Summary of a single chat session for the thread list."""

    key: str
    """Session key in the format 'channel:chat_id', e.g. 'web:abc-123'."""
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0
    channel: str = ""
    chat_id: str = ""
    title: str | None = None
    """Human-readable title, set via PATCH /api/sessions/{id} or auto-generated."""


class ToolCallRecord(BaseModel):
    """A tool call recorded in session history."""

    name: str
    arguments: dict[str, Any] = {}
    result: str | None = None


class MessageRecord(BaseModel):
    """A single message in a session's history."""

    role: str
    """'user' or 'assistant'."""
    content: str
    timestamp: str | None = None
    tools_used: list[str] | None = None
    blocks: list[dict[str, Any]] | None = None
    """Full timeline for assistant messages: thinking, content, tool_call, approval_request (for auditability)."""


class SessionDetail(BaseModel):
    """Full session data including all messages."""

    key: str
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[MessageRecord] = []
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Status / meta models
# ---------------------------------------------------------------------------


class StatusResponse(BaseModel):
    """Backend health and configuration summary."""

    version: str
    model: str
    workspace: str
    channels_enabled: list[str]


class ChannelStatusItem(BaseModel):
    """Status of a single enabled channel."""

    name: str
    enabled: bool
    running: bool


class ChannelsResponse(BaseModel):
    """Status of all channels."""

    channels: list[ChannelStatusItem]


# ---------------------------------------------------------------------------
# WebSocket message models (for documentation -- actual frames are plain JSON)
# ---------------------------------------------------------------------------


class WsInboundMessage(BaseModel):
    """Frame sent from client to server over the WebSocket."""

    type: str
    """'message' | 'new_session' | 'ping'"""
    content: str | None = None
    session_id: str | None = None


class WsOutboundToken(BaseModel):
    """Streaming token delta emitted while the agent is generating."""

    type: str = "token"
    content: str
    session_id: str


class WsOutboundToolCall(BaseModel):
    """Tool invocation event."""

    type: str = "tool_call"
    name: str
    arguments: dict[str, Any]
    session_id: str


class WsOutboundToolResult(BaseModel):
    """Tool result event."""

    type: str = "tool_result"
    name: str
    result: str
    session_id: str


class WsOutboundThinking(BaseModel):
    """Reasoning/thinking token streamed by models that support it (e.g. Claude, Deepseek)."""

    type: str = "thinking"
    content: str
    session_id: str | None = None


class WsOutboundComplete(BaseModel):
    """Final assembled message after streaming finishes."""

    type: str = "message_complete"
    content: str
    session_id: str
    tools_used: list[str] = []


class WsOutboundError(BaseModel):
    """Error frame."""

    type: str = "error"
    content: str


class StreamAgentLoopResult(BaseModel):
    """Return value of stream_agent_loop."""

    final_content: str | None = None
    tools_used: list[str] = []


class StreamAgentLoopParams(BaseModel):
    """Parameters for stream_agent_loop. Pass a single object instead of many arguments."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core
    context_builder: Any  # ContextBuilder
    session: Any  # Session
    tool_registry: Any  # ToolRegistry
    model: str
    temperature: float
    max_tokens: int
    max_iterations: int
    memory_window: int
    user_message: str
    on_event: Callable[[dict[str, Any]], Awaitable[None]]

    # Channel
    channel: str = "web"
    chat_id: str = ""
    media: list[str] | None = None

    # LLM config
    api_key: str | None = None
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None

    # Tool policy / approval
    tool_policy: dict[str, str] | None = None
    request_approval: Callable[[str, dict[str, Any], str], Awaitable[tuple[bool, str | None]]] | None = None
    generate_approval_title: Callable[[str, dict[str, Any]], Awaitable[str]] | None = None
    is_allowlisted: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None
    # CUA auto-approve: desktop tools + run_python after fast safety check
    cua_auto_approve: bool = False
    cua_safety_model: str = ""
    cua_safety_api_key: str | None = None

    # Resilience
    max_llm_retries: int = 3
    retry_backoff_base_seconds: int = 2
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 60.0

    # Tool execution timeout (0 = no timeout)
    tool_timeout_seconds: int = 0

    # Optional output
    collected_blocks: list[dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Session mutation request models
# ---------------------------------------------------------------------------


class EditMessageRequest(BaseModel):
    """Request body for editing a message in a session."""

    message_index: int
    """Index to truncate at: messages[message_index:] are removed."""
    new_content: str
    """The replacement user message content that will be sent next."""


class BranchSessionRequest(BaseModel):
    """Request body for branching a session from a specific message."""

    message_index: int
    """Inclusive index: messages[0..message_index] are copied into the new branch."""


class WebhookTriggerRequest(BaseModel):
    """Request body for triggering the agent via webhook (e.g. GitHub, IFTTT)."""

    message: str = ""
    prompt: str = ""
    """Use message or prompt as the task for the agent."""


class MemoryResponse(BaseModel):
    """Contents of MEMORY.md and HISTORY.md for the Session Management Dashboard."""

    memory: str = ""
    """Long-term facts (MEMORY.md)."""
    history: str = ""
    """History log (HISTORY.md)."""


class MemoryLongTermPut(BaseModel):
    """Request body for PUT /api/memory/long-term (overwrite MEMORY.md)."""

    content: str = ""


class MemoryHistoryPut(BaseModel):
    """Request body for PUT /api/memory/history (overwrite HISTORY.md)."""

    content: str = ""


class MemoryHistoryAppendRequest(BaseModel):
    """Request body for POST /api/memory/history/append."""

    entry: str = ""


class VerifyBulletRequest(BaseModel):
    """Request body for POST /api/memory/tasks/verify-bullet."""

    text: str = ""


class VerifyBulletResponse(BaseModel):
    """Response from verify-bullet task."""

    verified: bool
    comment: str


class ScanIrrelevantHistoryResponse(BaseModel):
    """Response from scan-irrelevant-history task."""

    irrelevant_indices: list[int] = []
    reasons: dict[int, str] = {}


class MemoryHistoryRemoveEntriesRequest(BaseModel):
    """Request body for POST /api/memory/history/remove-entries."""

    indices: list[int] = []


class MemoryChunkItem(BaseModel):
    """A single long-term memory chunk (vector DB)."""

    id: str
    document: str
    metadata: dict[str, Any] = {}


class MemoryChunksListResponse(BaseModel):
    """Paginated list of long-term memory chunks."""

    chunks: list[MemoryChunkItem] = []
    total: int = 0


class MemoryChunkUpdateRequest(BaseModel):
    """Request body for PATCH /api/memory/chunks/{id}."""

    document: str = ""


class MemoryChunksDeleteRequest(BaseModel):
    """Request body for DELETE /api/memory/chunks."""

    ids: list[str] = []


# ---------------------------------------------------------------------------
# Knowledge base (KG triples + RAG chunks)
# ---------------------------------------------------------------------------


class TripleItem(BaseModel):
    """A single knowledge graph triple."""

    id: int
    subject: str
    predicate: str
    object: str
    created_at: str = ""


class TriplesListResponse(BaseModel):
    """Paginated list of triples."""

    triples: list[TripleItem] = []
    total: int = 0


class TriplesStatsResponse(BaseModel):
    """Stats for KG (total and by predicate)."""

    total: int = 0
    by_predicate: dict[str, int] = {}


class TriplesDeleteRequest(BaseModel):
    """Request body for DELETE /api/knowledge/triples."""

    ids: list[int] = []


class RagChunkItem(BaseModel):
    """A single RAG chunk."""

    id: str
    document: str
    metadata: dict[str, Any] = {}


class RagChunksListResponse(BaseModel):
    """Paginated list of RAG chunks."""

    chunks: list[RagChunkItem] = []
    total: int = 0


class RagSourcesResponse(BaseModel):
    """Distinct RAG source paths."""

    sources: list[str] = []


class RagChunksDeleteRequest(BaseModel):
    """Request body for DELETE /api/knowledge/rag/chunks."""

    ids: list[str] = []


class AuthLoginRequest(BaseModel):
    """Request body for POST /auth/login (single-user: password = gateway.jwt_secret)."""

    password: str = ""


class RenameSessionRequest(BaseModel):
    """Request body for renaming a session."""

    title: str


class SessionProjectPatch(BaseModel):
    """Request body for setting the active project on a session."""

    project: str | None = None
    """Project name from GET /api/projects. Set to null to clear."""


class AllowlistEntry(BaseModel):
    """A single allowlist entry (tool + pattern)."""

    tool: str
    pattern: str


class AllowlistResponse(BaseModel):
    """List of allowlist entries."""

    entries: list[AllowlistEntry] = []


class AllowlistAddRequest(BaseModel):
    """Request to add an entry to the tool approval allowlist."""

    tool: str
    pattern: str


# ---------------------------------------------------------------------------
# Config models (safe subset exposed to frontend)
# ---------------------------------------------------------------------------


class MCPServerConfigResponse(BaseModel):
    """Safe representation of an MCP server config."""

    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    url: str = ""


class ModelOption(BaseModel):
    """A single selectable LLM model."""

    id: str
    """Full model string used by litellm, e.g. 'gemini/gemini-2.0-flash'."""
    label: str
    provider: str
    """Provider id from GET /api/providers; used for contextual model filtering."""


class ProviderItem(BaseModel):
    """A single LLM provider for the Provider selector."""

    id: str
    """Provider key, e.g. 'gemini', 'anthropic'."""
    display_name: str
    has_api_key: bool


class ProvidersResponse(BaseModel):
    """List of providers for the settings Provider selector."""

    providers: list[ProviderItem] = []


class ModelsResponse(BaseModel):
    """List of available models grouped by provider."""

    models: list[ModelOption] = []
    current: str
    """The currently configured model."""


class AgentConfigResponse(BaseModel):
    """Subset of agent config exposed to frontend."""

    model: str
    max_tokens: int
    temperature: float
    max_tool_iterations: int
    memory_window: int
    workspace: str
    """Raw workspace path (may contain ~ or relative refs)."""


class ToolsConfigResponse(BaseModel):
    """Subset of tools config exposed to frontend."""

    restrict_to_workspace: bool
    exec_timeout: int
    web_search_api_key_set: bool
    tool_policy: dict[str, str]
    """Effective per-tool policy overrides. See DEFAULT_TOOL_POLICY in routes.py."""
    mcp_guidance: dict[str, str] = Field(default_factory=dict)
    cua_auto_approve: bool = False
    """When True, desktop tools and safe run_python (validated by Groq) are auto-approved."""
    cua_safety_model: str = "llama-3.1-8b-instant"
    """Per-MCP-server guidance (server name → markdown). Injected into agent system prompt."""


class ProviderConfigResponse(BaseModel):
    """Safe view of one provider (no raw API key)."""

    api_key_set: bool = False
    api_base: str | None = None


class KgDedupConfigResponse(BaseModel):
    """De-duplicator (knowledge graph) config exposed to frontend."""

    enabled: bool = False
    schedule: str = "0 3 * * *"
    kg_dedup_model: str = ""
    """LLM for merge decisions; if empty, use memory_model."""
    llm_batch_size: int = 20
    batch_size: int = 256


class ConfigResponse(BaseModel):
    """Safe config snapshot returned by GET /api/config."""

    agent: AgentConfigResponse
    tools: ToolsConfigResponse
    kg_dedup: KgDedupConfigResponse = Field(default_factory=KgDedupConfigResponse)
    mcp_servers: dict[str, MCPServerConfigResponse] = {}
    providers: dict[str, ProviderConfigResponse] = {}
    """Per-provider state: api_key_set (masked), api_base. Keys match provider ids from GET /api/providers."""
    workspace: str
    version: str


class AgentConfigPatch(BaseModel):
    """Patchable agent settings."""

    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    max_tool_iterations: int | None = None
    memory_window: int | None = None
    workspace: str | None = None
    """Raw workspace path. Takes effect on next server restart."""


class MCPServerPatch(BaseModel):
    """An MCP server entry to add or update."""

    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    url: str = ""


class ProviderConfigPatch(BaseModel):
    """Patch for one provider's API key / base."""

    api_key: str | None = None
    """Set to update or clear the key; omit to leave unchanged."""
    api_base: str | None = None
    """Set to update or clear the base URL; omit to leave unchanged."""


class KgDedupConfigPatch(BaseModel):
    """Patchable de-duplicator settings."""

    enabled: bool | None = None
    schedule: str | None = None
    kg_dedup_model: str | None = None
    llm_batch_size: int | None = None
    batch_size: int | None = None


class KgDedupRestoreRequest(BaseModel):
    """Request body for POST /api/kg-dedup/restore (restore a removed triple)."""

    subject: str = ""
    predicate: str = ""
    object: str = ""


class LlmProfilerResponse(BaseModel):
    """Response from POST /api/llm/profiler (test connection and stream metrics)."""

    ok: bool
    error: str | None = None
    """When ok is False, the error message from the LLM call."""
    time_to_first_token_ms: int | None = None
    """Milliseconds from request start to first content or reasoning chunk."""
    tokens_per_second: float | None = None
    """Approximate tokens per second (chars/4 over stream duration)."""
    has_thinking_stream: bool = False
    """True if the model returned reasoning_content / thinking chunks."""


class ConfigPatch(BaseModel):
    """Fields the frontend can update via PATCH /api/config."""

    agent: AgentConfigPatch | None = None
    providers: dict[str, ProviderConfigPatch] | None = None
    """Per-provider API keys and optional api_base. Keys: gemini, anthropic, openai, etc."""
    kg_dedup: KgDedupConfigPatch | None = None
    restrict_to_workspace: bool | None = None
    exec_timeout: int | None = None
    web_search_api_key: str | None = None
    mcp_servers: dict[str, MCPServerPatch | None] | None = None
    """Pass null value for a key to remove that MCP server."""
    mcp_guidance: dict[str, str] | None = None
    """Per-MCP-server guidance (server name → markdown). Replaces existing when provided."""
    tool_policy: dict[str, str] | None = None
    """Per-tool policy overrides. Values: 'auto' | 'ask' | 'deny'."""
    cua_auto_approve: bool | None = None
    """When True, desktop tools and safe run_python (Groq-validated) are auto-approved."""
    cua_safety_model: str | None = None
    """Model for CUA run_python safety check (e.g. llama-3.1-8b-instant)."""


# ---------------------------------------------------------------------------
# Cron / scheduled jobs (dashboard)
# ---------------------------------------------------------------------------


class CronScheduleSummary(BaseModel):
    """Human-readable schedule summary for display."""

    kind: str
    """'at' | 'every' | 'cron'."""
    summary: str
    """e.g. 'Every 3600s', '0 9 * * *', 'At 2026-02-20 09:00'."""


class CronJobStateResponse(BaseModel):
    """Runtime state of a cron job."""

    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_status: str | None = None
    """'ok' | 'error' | 'skipped'."""
    last_error: str | None = None


class CronJobItem(BaseModel):
    """A single scheduled job for the dashboard."""

    id: str
    name: str
    enabled: bool
    schedule: CronScheduleSummary
    state: CronJobStateResponse
    message: str = ""
    """Payload message (what the agent runs with)."""
    is_system_job: bool = False
    """True for system_event jobs (e.g. memory_sleep, kg_dedup); they cannot be deleted."""


class CronJobPatch(BaseModel):
    """Request body for PATCH /api/cron/jobs/{job_id}."""

    enabled: bool | None = None
    """Enable or disable the job."""
    schedule_kind: Literal["every", "at", "cron"] | None = None
    """Change schedule: 'every' | 'at' | 'cron'."""
    interval_minutes: int | None = None
    run_at_iso: str | None = None
    cron_expr: str | None = None
    cron_tz: str | None = None


class CronJobCreateRequest(BaseModel):
    """Request body for POST /api/cron/jobs (create new scheduled task)."""

    name: str
    message: str
    """Prompt/message the agent runs when the job fires (prompt mode), or JSON input for workflow mode."""
    task_kind: Literal["prompt", "workflow"] = "prompt"
    """'prompt' = run agent with message; 'workflow' = run named workflow (name should be workflow:<id>, message = JSON input)."""
    workflow_id: str | None = None
    """For task_kind 'workflow': workflow id to run. If set, name is set to workflow:<id> unless name is explicitly provided."""
    workflow_input: dict[str, Any] | None = None
    """Optional input JSON for workflow run."""
    schedule_kind: Literal["every", "at", "cron"] = "every"
    """'every' = recurring interval; 'at' = run once at a specific time; 'cron' = cron expression."""
    interval_minutes: int = 60
    """Run every N minutes (used when schedule_kind is 'every'). Must be >= 1."""
    run_at_iso: str | None = None
    """For schedule_kind 'at': ISO datetime string (e.g. 2026-02-20T09:00:00) for one-off run."""
    cron_expr: str | None = None
    """For schedule_kind 'cron': cron expression (e.g. '0 9 * * *' for daily at 9am)."""
    cron_tz: str | None = None
    """Optional timezone for cron (e.g. 'America/New_York'). Defaults to local."""
    delete_after_run: bool = False
    """For 'at' jobs: remove job after it runs once."""
