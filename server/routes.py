"""
REST API routes for the nanobot web server.

All endpoints access nanobot components via app.state references set in
app.py. No nanobot source files are modified.

Endpoint runbook (add new endpoints by following this pattern):
  1. Define request/response models in models.py
  2. Add route function here
  3. Add TypeScript type in frontend/src/api/types.ts
  4. Add client method in frontend/src/api/client.ts
  5. Wire to UI component or Zustand store
"""

from __future__ import annotations

from fastapi import APIRouter, Body, File, Header, Request, UploadFile  # noqa: I001

from server.auth import AuthUser
from server.handlers import allowlist as allowlist_handlers
from server.handlers import auth as auth_handlers
from server.handlers import config as config_handlers
from server.handlers import cron as cron_handlers
from server.handlers import kg_dedup as kg_dedup_handlers
from server.handlers import llm as llm_handlers
from server.handlers import mcp as mcp_handlers
from server.handlers import knowledge as knowledge_handlers
from server.handlers import media as media_handlers
from server.handlers import memory as memory_handlers
from server.handlers import memory_chunks as memory_chunks_handlers
from server.handlers import sessions as sessions_handlers
from server.handlers import webhooks as webhooks_handlers
from server.handlers import workflows as workflow_handlers
from server.models import (
    AllowlistAddRequest,
    AllowlistResponse,
    AuthLoginRequest,
    BranchSessionRequest,
    ChannelsResponse,
    ConfigPatch,
    ConfigResponse,
    CronJobCreateRequest,
    CronJobItem,
    CronJobPatch,
    EditMessageRequest,
    KgDedupRestoreRequest,
    LlmProfilerResponse,
    MemoryChunkItem,
    MemoryChunksDeleteRequest,
    MemoryChunksListResponse,
    MemoryChunkUpdateRequest,
    MemoryHistoryAppendRequest,
    MemoryHistoryPut,
    MemoryHistoryRemoveEntriesRequest,
    MemoryLongTermPut,
    MemoryResponse,
    ModelsResponse,
    ProvidersResponse,
    RagChunksDeleteRequest,
    RagChunksListResponse,
    RagSourcesResponse,
    RenameSessionRequest,
    ScanIrrelevantHistoryResponse,
    SessionDetail,
    SessionListItem,
    SessionProjectPatch,
    StatusResponse,
    TriplesDeleteRequest,
    TriplesListResponse,
    TriplesStatsResponse,
    VerifyBulletRequest,
    VerifyBulletResponse,
    WebhookTriggerRequest,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.post("/auth/login")
async def auth_login(request: Request, body: AuthLoginRequest) -> dict:
    """Exchange password for JWT when auth_enabled and jwt_secret are set."""
    return await auth_handlers.auth_login(request, body)


# ---------------------------------------------------------------------------
# Media (upload / serve)
# ---------------------------------------------------------------------------

@router.get("/media")
async def serve_media(request: Request, path: str = ""):
    """Serve an uploaded file by path (e.g. path=media/abc.png). Only under data dir."""
    return await media_handlers.serve_media(request, path)


@router.post("/upload", response_model=dict)
async def upload_file(file: UploadFile = File(...)) -> dict:
    """Upload a file for message attachment. Returns path relative to data dir."""
    return await media_handlers.upload_file(file)


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(auth_user: AuthUser, request: Request, q: str | None = None) -> list[SessionListItem]:
    """List all chat sessions with summary metadata. Optional q filters by title, chat_id, or key."""
    return await sessions_handlers.list_sessions(request, auth_user, q)


@router.get("/sessions/{session_id:path}", response_model=SessionDetail)
async def get_session(session_id: str, request: Request, auth_user: AuthUser) -> SessionDetail:
    """Get full session history including all messages and tool usage."""
    return await sessions_handlers.get_session(session_id, request, auth_user)


@router.delete("/sessions/{session_id:path}", response_model=dict)
async def delete_session(session_id: str, request: Request, auth_user: AuthUser) -> dict:
    """Permanently delete a session (removes the JSONL file from disk and cache)."""
    return await sessions_handlers.delete_session(session_id, request, auth_user)


@router.patch("/sessions/{session_id:path}/rename", response_model=dict)
async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    request: Request,
    auth_user: AuthUser,
) -> dict:
    """Rename a session by setting a human-readable title in its metadata."""
    return await sessions_handlers.rename_session(session_id, body, request, auth_user)


@router.get("/projects", response_model=list[dict])
async def list_projects(request: Request) -> list[dict]:
    """List projects from ~/.nanobot/projects.json for the Project Context Switcher."""
    return await sessions_handlers.list_projects(request)


@router.patch("/sessions/{session_id:path}/project", response_model=dict)
async def set_session_project(
    session_id: str,
    body: SessionProjectPatch,
    request: Request,
    auth_user: AuthUser,
) -> dict:
    """Set or clear the active project for this session (stored in session metadata)."""
    return await sessions_handlers.set_session_project(session_id, body, request, auth_user)


@router.post("/sessions/{session_id:path}/retry", response_model=dict)
async def retry_session(session_id: str, request: Request, auth_user: AuthUser) -> dict:
    """Branch from last user message; returns new key and message count."""
    return await sessions_handlers.retry_session(session_id, request, auth_user)


@router.post("/sessions/{session_id:path}/branch", response_model=dict)
async def branch_session(
    session_id: str,
    body: BranchSessionRequest,
    request: Request,
    auth_user: AuthUser,
) -> dict:
    """Branch from a specific message into a new session."""
    return await sessions_handlers.branch_session(session_id, body, request, auth_user)


@router.post("/sessions/{session_id:path}/edit", response_model=dict)
async def edit_session_message(
    session_id: str,
    body: EditMessageRequest,
    request: Request,
    auth_user: AuthUser,
) -> dict:
    """Truncate session to message_index (exclusive); frontend sends new_content as new message."""
    return await sessions_handlers.edit_session_message(session_id, body, request, auth_user)


# ---------------------------------------------------------------------------
# Tool approval allowlist
# ---------------------------------------------------------------------------

@router.get("/allowlist", response_model=AllowlistResponse)
async def get_allowlist(auth_user: AuthUser) -> AllowlistResponse:
    """List all allowlist entries (tool + pattern)."""
    return await allowlist_handlers.get_allowlist(auth_user)


@router.post("/allowlist", response_model=dict)
async def add_allowlist_entry(body: AllowlistAddRequest, auth_user: AuthUser) -> dict:
    """Add an entry to the allowlist."""
    return await allowlist_handlers.add_allowlist_entry(body, auth_user)


@router.delete("/allowlist", response_model=dict)
async def remove_allowlist_entry(body: AllowlistAddRequest, auth_user: AuthUser) -> dict:
    """Remove an allowlist entry."""
    return await allowlist_handlers.remove_allowlist_entry(body, auth_user)


@router.post("/sessions/{session_id:path}/new", response_model=dict)
async def new_session(session_id: str, request: Request, auth_user: AuthUser) -> dict:
    """Start a new conversation in a session (clears history)."""
    return await sessions_handlers.new_session(session_id, request, auth_user)


# ---------------------------------------------------------------------------
# Webhook trigger
# ---------------------------------------------------------------------------

@router.post("/webhooks/trigger")
async def webhook_trigger(
    request: Request,
    body: WebhookTriggerRequest,
    x_webhook_token: str | None = Header(None, alias="X-Webhook-Token"),
) -> dict:
    """Trigger the agent with a message (e.g. from GitHub, IFTTT). Returns 202 with job_id."""
    return await webhooks_handlers.webhook_trigger(request, body, x_webhook_token)


# ---------------------------------------------------------------------------
# Memory (MEMORY.md / HISTORY.md)
# ---------------------------------------------------------------------------

@router.get("/memory", response_model=MemoryResponse)
async def get_memory(request: Request, auth_user: AuthUser) -> MemoryResponse:
    """Read MEMORY.md and HISTORY.md from the workspace memory directory."""
    return await memory_handlers.get_memory(request, auth_user)


@router.put("/memory/long-term", response_model=dict)
async def put_memory_long_term(
    request: Request, body: MemoryLongTermPut, auth_user: AuthUser
) -> dict:
    """Overwrite MEMORY.md with the given content."""
    return await memory_handlers.put_memory_long_term(request, body, auth_user)


@router.put("/memory/history", response_model=dict)
async def put_memory_history(
    request: Request, body: MemoryHistoryPut, auth_user: AuthUser
) -> dict:
    """Overwrite HISTORY.md with the given content."""
    return await memory_handlers.put_memory_history(request, body, auth_user)


@router.post("/memory/history/append", response_model=dict)
async def post_memory_history_append(
    request: Request, body: MemoryHistoryAppendRequest, auth_user: AuthUser
) -> dict:
    """Append one entry to HISTORY.md."""
    return await memory_handlers.post_memory_history_append(request, body, auth_user)


@router.post("/memory/tasks/verify-bullet", response_model=VerifyBulletResponse)
async def post_memory_tasks_verify_bullet(
    request: Request, body: VerifyBulletRequest, auth_user: AuthUser
) -> VerifyBulletResponse:
    """Ask LLM whether the given bullet/fact is still accurate."""
    return await memory_handlers.post_memory_tasks_verify_bullet(request, body, auth_user)


@router.post("/memory/tasks/scan-irrelevant-history", response_model=ScanIrrelevantHistoryResponse)
async def post_memory_tasks_scan_irrelevant_history(
    request: Request, auth_user: AuthUser
) -> ScanIrrelevantHistoryResponse:
    """Ask LLM to identify irrelevant HISTORY.md entries."""
    return await memory_handlers.post_memory_tasks_scan_irrelevant_history(request, auth_user)


@router.post("/memory/history/remove-entries", response_model=dict)
async def post_memory_history_remove_entries(
    request: Request, body: MemoryHistoryRemoveEntriesRequest, auth_user: AuthUser
) -> dict:
    """Remove HISTORY.md entries by 0-based index."""
    return await memory_handlers.post_memory_history_remove_entries(request, body, auth_user)


# ---------------------------------------------------------------------------
# Long-term memory chunks
# ---------------------------------------------------------------------------

@router.get("/memory/chunks", response_model=MemoryChunksListResponse)
async def get_memory_chunks(
    request: Request,
    auth_user: AuthUser,
    limit: int = 50,
    offset: int = 0,
    run_id: str | None = None,
    date: str | None = None,
) -> MemoryChunksListResponse:
    """List long-term memory chunks with optional filters and pagination."""
    return await memory_chunks_handlers.get_memory_chunks(
        request, auth_user, limit, offset, run_id, date
    )


@router.get("/memory/chunks/{chunk_id:path}", response_model=MemoryChunkItem)
async def get_memory_chunk(
    chunk_id: str, request: Request, auth_user: AuthUser
) -> MemoryChunkItem:
    """Get a single long-term memory chunk by id."""
    return await memory_chunks_handlers.get_memory_chunk(chunk_id, request, auth_user)


@router.patch("/memory/chunks/{chunk_id:path}", response_model=dict)
async def patch_memory_chunk(
    chunk_id: str,
    request: Request,
    body: MemoryChunkUpdateRequest,
    auth_user: AuthUser,
) -> dict:
    """Update a chunk's document and re-embed."""
    return await memory_chunks_handlers.patch_memory_chunk(
        chunk_id, request, body, auth_user
    )


@router.delete("/memory/chunks", response_model=dict)
async def delete_memory_chunks(
    request: Request, body: MemoryChunksDeleteRequest, auth_user: AuthUser
) -> dict:
    """Delete long-term memory chunks by id."""
    return await memory_chunks_handlers.delete_memory_chunks(request, body, auth_user)


# ---------------------------------------------------------------------------
# Knowledge base (KG triples + RAG chunks)
# ---------------------------------------------------------------------------

@router.get("/knowledge/triples", response_model=TriplesListResponse)
async def get_knowledge_triples(
    auth_user: AuthUser,
    subject: str | None = None,
    predicate: str | None = None,
    object: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> TriplesListResponse:
    """List knowledge graph triples with optional substring filters."""
    return await knowledge_handlers.get_knowledge_triples(
        auth_user, subject, predicate, object_=object, limit=limit, offset=offset
    )


@router.get("/knowledge/triples/stats", response_model=TriplesStatsResponse)
async def get_knowledge_triples_stats(auth_user: AuthUser) -> TriplesStatsResponse:
    """Return total triple count and counts by predicate."""
    return await knowledge_handlers.get_knowledge_triples_stats(auth_user)


@router.delete("/knowledge/triples", response_model=dict)
async def delete_knowledge_triples(
    request: Request, body: TriplesDeleteRequest, auth_user: AuthUser
) -> dict:
    """Delete triples by primary key."""
    return await knowledge_handlers.delete_knowledge_triples(
        request, body, auth_user
    )


@router.get("/knowledge/rag/chunks", response_model=RagChunksListResponse)
async def get_knowledge_rag_chunks(
    request: Request,
    auth_user: AuthUser,
    limit: int = 50,
    offset: int = 0,
    source: str | None = None,
    q: str | None = None,
) -> RagChunksListResponse:
    """List RAG chunks. Use q for semantic search. Optional source filter."""
    return await knowledge_handlers.get_knowledge_rag_chunks(
        request, auth_user, limit, offset, source, q
    )


@router.get("/knowledge/rag/sources", response_model=RagSourcesResponse)
async def get_knowledge_rag_sources(
    request: Request, auth_user: AuthUser
) -> RagSourcesResponse:
    """List distinct RAG source paths."""
    return await knowledge_handlers.get_knowledge_rag_sources(request, auth_user)


@router.delete("/knowledge/rag/chunks", response_model=dict)
async def delete_knowledge_rag_chunks(
    request: Request, body: RagChunksDeleteRequest, auth_user: AuthUser
) -> dict:
    """Delete RAG chunks by id."""
    return await knowledge_handlers.delete_knowledge_rag_chunks(
        request, body, auth_user
    )


# ---------------------------------------------------------------------------
# Status / config
# ---------------------------------------------------------------------------

@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request) -> StatusResponse:
    """Return backend health and configuration summary."""
    return await config_handlers.get_status(request)


@router.get("/channels", response_model=ChannelsResponse)
async def get_channels(request: Request) -> ChannelsResponse:
    """Return the status of all enabled chat channels."""
    return await config_handlers.get_channels(request)


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers(request: Request) -> ProvidersResponse:
    """Return list of LLM providers with display names and API key status."""
    return await config_handlers.get_providers(request)


@router.get("/models", response_model=ModelsResponse)
async def get_models(request: Request) -> ModelsResponse:
    """Return available models based on which providers have API keys."""
    return await config_handlers.get_models(request)


@router.get("/config", response_model=ConfigResponse)
async def get_config(request: Request, auth_user: AuthUser) -> ConfigResponse:
    """Return a safe subset of the nanobot config (no raw API keys)."""
    return await config_handlers.get_config(request, auth_user)


@router.patch("/config", response_model=dict)
async def patch_config(
    body: ConfigPatch, request: Request, auth_user: AuthUser
) -> dict:
    """Update writable config fields and persist to ~/.nanobot/config.json."""
    return await config_handlers.patch_config(body, request, auth_user)


# ---------------------------------------------------------------------------
# LLM profiler (test connection, stream metrics)
# ---------------------------------------------------------------------------

@router.post("/llm/profiler", response_model=LlmProfilerResponse)
async def post_llm_profiler(request: Request, auth_user: AuthUser) -> LlmProfilerResponse:
    """Run a minimal streaming completion; return connection and stream metrics."""
    return await llm_handlers.post_llm_profiler(request)


# ---------------------------------------------------------------------------
# MCP connection status and test
# ---------------------------------------------------------------------------

@router.get("/mcp/status", response_model=dict)
async def mcp_status(request: Request, auth_user: AuthUser) -> dict:
    """List all configured MCP servers with connection status and which workflows use them."""
    return await mcp_handlers.get_mcp_status(request)


@router.get("/mcp/status/{server_key}", response_model=dict)
async def mcp_server_status(server_key: str, request: Request, auth_user: AuthUser) -> dict:
    """Return status for a single MCP server (for per-server loading in UI)."""
    return await mcp_handlers.get_mcp_server_status(server_key, request)


@router.post("/mcp/test/{server_key}", response_model=dict)
async def mcp_test(server_key: str, request: Request, auth_user: AuthUser) -> dict:
    """Test connection to one MCP server by key. Returns ok and tools_count or error."""
    return await mcp_handlers.test_mcp_connection(server_key, request)


@router.post("/mcp/servers/{server_key}/tools/invoke", response_model=dict)
async def mcp_invoke_tool(server_key: str, request: Request, auth_user: AuthUser) -> dict:
    """Invoke one MCP tool (sandbox: runs for real, no chat session). Body: { tool_name, arguments }."""
    return await mcp_handlers.invoke_mcp_tool(server_key, request)


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

@router.get("/workflows", response_model=list)
async def list_workflows_route(request: Request, auth_user: AuthUser) -> list:
    """List all registered workflows with last run info."""
    return await workflow_handlers.list_workflows_handler(request)


@router.get("/workflows/{workflow_id:path}", response_model=dict)
async def get_workflow_route(
    workflow_id: str, request: Request, auth_user: AuthUser
) -> dict:
    """Get full workflow definition by id."""
    return await workflow_handlers.get_workflow_handler(workflow_id, request)


@router.post("/workflows", response_model=dict)
async def create_workflow_route(
    request: Request,
    auth_user: AuthUser,
    body: dict = Body(default_factory=dict),
) -> dict:
    """Create a new workflow. Body: id?, name, description?, status?, nodes, edges."""
    return await workflow_handlers.create_workflow_handler(body, request)


@router.patch("/workflows/{workflow_id:path}", response_model=dict)
async def update_workflow_route(
    workflow_id: str,
    request: Request,
    auth_user: AuthUser,
    body: dict = Body(default_factory=dict),
) -> dict:
    """Update workflow definition (partial merge)."""
    return await workflow_handlers.update_workflow_handler(workflow_id, body, request)


@router.delete("/workflows/{workflow_id:path}", status_code=204)
async def delete_workflow_route(
    workflow_id: str, request: Request, auth_user: AuthUser
) -> None:
    """Permanently delete a workflow. Cannot be undone."""
    await workflow_handlers.delete_workflow_handler(workflow_id, request)


@router.post("/workflows/{workflow_id:path}/run", response_model=dict)
async def run_workflow_route(
    workflow_id: str,
    request: Request,
    auth_user: AuthUser,
    body: dict | None = Body(default=None),
) -> dict:
    """Run a workflow. Optional body: { \"input\": {...} }. Returns run_id."""
    return await workflow_handlers.run_workflow_handler(workflow_id, request, body)


@router.get("/workflow-runs", response_model=list)
async def list_workflow_runs_route(
    request: Request,
    auth_user: AuthUser,
    workflow_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list:
    """List workflow runs, optionally filtered by workflow_id."""
    return await workflow_handlers.list_workflow_runs_handler(
        request, workflow_id=workflow_id, limit=limit, offset=offset
    )


@router.get("/workflow-runs/{run_id:path}", response_model=dict)
async def get_workflow_run_route(
    run_id: str, request: Request, auth_user: AuthUser
) -> dict:
    """Get a single workflow run by run_id."""
    return await workflow_handlers.get_workflow_run_handler(run_id, request)


# ---------------------------------------------------------------------------
# Cron / scheduled jobs
# ---------------------------------------------------------------------------

@router.get("/cron/jobs", response_model=list[CronJobItem])
async def list_cron_jobs(request: Request, auth_user: AuthUser) -> list[CronJobItem]:
    """List all scheduled jobs (including disabled)."""
    return await cron_handlers.list_cron_jobs(request, auth_user)


@router.post("/cron/jobs", response_model=CronJobItem)
async def create_cron_job(
    body: CronJobCreateRequest,
    request: Request,
    auth_user: AuthUser,
) -> CronJobItem:
    """Create a new scheduled job."""
    return await cron_handlers.create_cron_job(body, request, auth_user)


@router.delete("/cron/jobs/{job_id}", status_code=204)
async def delete_cron_job(
    job_id: str, request: Request, auth_user: AuthUser
) -> None:
    """Remove a scheduled job by ID. System events cannot be deleted."""
    await cron_handlers.delete_cron_job(job_id, request, auth_user)


@router.patch("/cron/jobs/{job_id}", response_model=CronJobItem)
async def update_cron_job(
    job_id: str,
    body: CronJobPatch,
    request: Request,
    auth_user: AuthUser,
) -> CronJobItem:
    """Update a job: enable/disable and/or change schedule."""
    return await cron_handlers.update_cron_job(job_id, body, request, auth_user)


@router.post("/cron/jobs/{job_id}/run", response_model=dict)
async def run_cron_job(
    job_id: str,
    request: Request,
    auth_user: AuthUser,
) -> dict:
    """Run a cron job now (manual trigger). Works for workflow and agent_turn jobs."""
    return await cron_handlers.run_cron_job(job_id, request, auth_user)


# ---------------------------------------------------------------------------
# KG dedup (Admin)
# ---------------------------------------------------------------------------

@router.post("/kg-dedup/run", response_model=dict)
async def start_kg_dedup(request: Request, auth_user: AuthUser) -> dict:
    """Start KG deduplication in the background. Returns run_id; use stream for progress."""
    return await kg_dedup_handlers.start_kg_dedup(request, auth_user)


@router.get("/kg-dedup/stream")
async def stream_kg_dedup_progress(
    request: Request,
    run_id: str,
    auth_user: AuthUser,
):
    """SSE stream of progress events for a KG dedup run."""
    return await kg_dedup_handlers.stream_kg_dedup_progress(
        request, run_id, auth_user
    )


@router.get("/kg-dedup/audit", response_model=list)
async def list_kg_dedup_audits(request: Request, auth_user: AuthUser) -> list:
    """List recent KG dedup runs (from audit files)."""
    return await kg_dedup_handlers.list_kg_dedup_audits(request, auth_user)


@router.get("/kg-dedup/audit/{run_id}", response_model=dict)
async def get_kg_dedup_audit(
    run_id: str,
    request: Request,
    auth_user: AuthUser,
) -> dict:
    """Get full audit for a run (merged_nodes, removed_triples)."""
    return await kg_dedup_handlers.get_kg_dedup_audit(run_id, request, auth_user)


@router.post("/kg-dedup/restore", response_model=dict)
async def restore_kg_dedup_triple(
    body: KgDedupRestoreRequest,
    auth_user: AuthUser,
) -> dict:
    """Restore a triple that was removed during dedup."""
    return await kg_dedup_handlers.restore_kg_dedup_triple(body, auth_user)
