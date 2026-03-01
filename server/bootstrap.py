"""
Composition root for the nanobot web server.

Replicates the wiring logic from nanobot/cli/commands.py gateway command,
returning all components instead of running them directly. This lets the
FastAPI lifespan manage startup and shutdown.

All imports are from nanobot's public package API -- no nanobot source
files are modified.
"""

from __future__ import annotations

import asyncio
import json
import os  # noqa: I001

from loguru import logger

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.channels.manager import ChannelManager
from nanobot.config.loader import get_data_dir, load_config
from nanobot.config.schema import Config
from nanobot.cron.service import CronService
from nanobot.cron.types import CronJob, CronSchedule
from nanobot.heartbeat.service import HeartbeatService
from nanobot.session.manager import SessionManager
from server.agents.registry import build_workflow_summary, run_workflow
from server.agents.personal_os_tools import create_personal_os_tools
from server.agents.workflow_tools import create_workflow_tools
from server.db import load_workflow_definition, save_workflow_definition
from server.kg_dedup import run_kg_dedup_async
from server.memory_sleep import run_memory_sleep


def _ensure_x_engagement_workflow(data_dir) -> None:
    """Create the X Engagement Assistant workflow definition if it does not exist."""
    wf_id = "x_engagement"
    if load_workflow_definition(data_dir, wf_id) is not None:
        return
    definition = {
        "id": wf_id,
        "name": "X Engagement Assistant",
        "description": "Log in to X, review analytics, analyze feed, select top 10 posts, deliver to user via Personal OS.",
        "status": "active",
        "idempotent": "day",
        "nodes": [
            {
                "id": "auth",
                "name": "Auth",
                "type": "nanobot",
                "prompt": "Use the Playwright MCP tools and credentials from Bitwarden (resolve X login item) to log in to X (twitter.com). Persist session so re-auth is only needed when the session expires. Confirm when logged in.",
            },
            {
                "id": "analytics",
                "name": "Analytics",
                "type": "nanobot",
                "prompt": "Navigate to X Analytics and capture key performance metrics for the recent period. Analyze the data and identify patterns and insights in top engaging content (topics, formats, timing). Summarize the insights briefly.",
            },
            {
                "id": "feed_analysis",
                "name": "Feed analysis",
                "type": "nanobot",
                "prompt": "Navigate to the X home feed and analyze at least 50 posts. Using the analytics insights from the prior step, select the top 10 posts most worth engaging with. For each selected post provide: post URL, author, content snippet, visible engagement metrics, and a brief reason why it is worth engaging with.",
            },
            {
                "id": "delivery",
                "name": "Delivery",
                "type": "nanobot",
                "prompt": "You have analytics insights and the top 10 posts from the previous steps in the graph state. 1) Log that this run completed (the system will persist the result). 2) Use personal_os_send_message to send the user a message containing the analytics insights and the 10 posts with direct links, formatted for easy review. 3) Use personal_os_create_task to create a task titled 'Review and act on morning engagement list'. Respond with a short confirmation that delivery is done.",
            },
        ],
        "edges": [
            {"from": "auth", "to": "analytics"},
            {"from": "analytics", "to": "feed_analysis"},
            {"from": "feed_analysis", "to": "delivery"},
            {"from": "delivery", "to": "__end__"},
        ],
    }
    save_workflow_definition(data_dir, wf_id, definition)
    logger.info("Created default X Engagement Assistant workflow")


def _make_provider(config: Config):
    """
    Create an LLM provider from config.

    Mirrors _make_provider() in nanobot/cli/commands.py exactly.
    Raises SystemExit if no API key is configured.
    """
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    if not model.startswith("bedrock/") and not (p and p.api_key):
        raise RuntimeError(
            "No API key configured. "
            "Set one in ~/.nanobot/config.json under the providers section."
        )

    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
        max_retries=getattr(config.agents.defaults, "max_llm_retries", 3),
        retry_backoff_base_seconds=getattr(config.agents.defaults, "retry_backoff_base_seconds", 2),
    )


def bootstrap() -> tuple[
    Config,
    MessageBus,
    AgentLoop,
    SessionManager,
    ChannelManager,
    CronService,
    HeartbeatService,
]:
    """
    Compose all nanobot components needed to run the web server.

    Returns a tuple of (config, bus, agent, session_manager, channels, cron, heartbeat).
    All components are wired together but not yet started -- startup happens
    inside the FastAPI lifespan context manager in app.py.
    """
    config = load_config()
    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)

    data_dir = get_data_dir()
    cron_store_path = data_dir / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=getattr(config.agents.defaults, "reasoning_effort", None),
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        python_inline_config=config.tools.python_inline,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        mcp_servers=config.tools.mcp_servers,
        mcp_guidance=config.tools.mcp_guidance,
        tool_timeout_seconds=getattr(config.tools, "tool_timeout_seconds", 0) or 0,
        cua_auto_approve=getattr(config.tools, "cua_auto_approve", False),
        screenshot_follow_up_text=getattr(config.tools, "screenshot_follow_up_text", None) or None,
        computer_use_config=getattr(config.tools, "computer_use", None),
        computer_use_confirm_callback=None,
        computer_use_api_key=(
            (os.environ.get("GEMINI_API_KEY") or getattr(config.tools.computer_use, "api_key", None) or config.get_api_key("gemini/gemini-3-flash-preview") or None)
            if getattr(config.tools, "computer_use", None) and getattr(config.tools.computer_use, "enabled", False)
            else None
        ),
    )

    # Register workflow tools so the agent can list, run, create, and update workflows
    for tool in create_workflow_tools(data_dir, agent):
        agent.tools.register(tool)
    for tool in create_personal_os_tools():
        agent.tools.register(tool)

    # Inject workflow summary into agent context (describe workflows without loading full defs)
    agent.context.workflow_summary_callback = lambda: build_workflow_summary(data_dir)

    # Ensure X Engagement Assistant workflow exists (default definition)
    _ensure_x_engagement_workflow(data_dir)

    # Wire cron callback (needs agent reference). Timeout to avoid hung tool calls.
    CRON_JOB_TIMEOUT_S = 300  # 5 minutes
    MEMORY_SLEEP_TIMEOUT_S = 600  # 10 minutes for sleep pipeline
    KG_DEDUP_TIMEOUT_S = 900  # 15 minutes for KG dedup

    async def handle_memory_sleep(job: CronJob) -> str | None:
        try:
            result = await asyncio.wait_for(
                run_memory_sleep(config.workspace_path, config),
                timeout=MEMORY_SLEEP_TIMEOUT_S,
            )
            return result or "memory_sleep completed with warnings"
        except asyncio.TimeoutError:
            raise Exception(f"Memory sleep timed out after {MEMORY_SLEEP_TIMEOUT_S}s.")
        except Exception as e:
            raise Exception(f"Memory sleep failed: {e}")

    async def handle_kg_dedup(job: CronJob) -> str | None:
        kg_path = data_dir / "memory" / "knowledge_graph.db"
        audit_dir = data_dir / "memory" / "kg_dedup_audit"
        kg_cfg = getattr(config, "kg_dedup", None)
        batch_size = getattr(kg_cfg, "batch_size", 256) if kg_cfg else 256
        llm_batch_size = getattr(kg_cfg, "llm_batch_size", 20) if kg_cfg else 20
        try:
            result = await asyncio.wait_for(
                run_kg_dedup_async(
                    kg_path,
                    config,
                    batch_size=batch_size,
                    llm_batch_size=llm_batch_size,
                    audit_dir=audit_dir,
                ),
                timeout=KG_DEDUP_TIMEOUT_S,
            )
            if result.get("error"):
                return f"kg_dedup: {result['error']}"
            return (
                f"kg_dedup: triples {result.get('triples_before', 0)} -> {result.get('triples_after', 0)}, "
                f"bloat saved {result.get('bloat_saved_pct', 0)}%"
            )
        except asyncio.TimeoutError:
            raise Exception(f"KG dedup timed out after {KG_DEDUP_TIMEOUT_S}s.")
        except Exception as e:
            raise Exception(f"KG dedup failed: {e}")

    SYSTEM_EVENT_HANDLERS = {
        "memory_sleep": handle_memory_sleep,
        "kg_dedup": handle_kg_dedup,
    }

    WORKFLOW_JOB_TIMEOUT_S = 600  # 10 minutes for workflow runs

    async def on_cron_job(job: CronJob) -> str | None:
        kind = getattr(job.payload, "kind", None)
        is_system_event = kind == "system_event" or (job.name == "memory_sleep" and kind == "memory_sleep")
        if is_system_event and job.name in SYSTEM_EVENT_HANDLERS:
            return await SYSTEM_EVENT_HANDLERS[job.name](job)

        # Workflow jobs: job.name is "workflow:<workflow_id>", payload.message is optional JSON input
        if job.name.startswith("workflow:"):
            workflow_id = job.name.split(":", 1)[1].strip()
            input_payload = {}
            if getattr(job.payload, "message", ""):
                try:
                    input_payload = json.loads(job.payload.message)
                except json.JSONDecodeError:
                    pass
            try:
                run_id = await asyncio.wait_for(
                    run_workflow(data_dir, workflow_id, agent, input_payload),
                    timeout=WORKFLOW_JOB_TIMEOUT_S,
                )
                return f"workflow run {run_id} completed"
            except asyncio.TimeoutError:
                raise Exception(
                    f"Workflow job timed out after {WORKFLOW_JOB_TIMEOUT_S}s."
                )
            except Exception as e:
                raise Exception(f"Workflow {workflow_id} failed: {e}")

        try:
            response = await asyncio.wait_for(
                agent.process_direct(
                    job.payload.message,
                    session_key=f"cron:{job.id}",
                    channel=job.payload.channel or "cli",
                    chat_id=job.payload.to or "direct",
                ),
                timeout=CRON_JOB_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            raise Exception(
                f"Cron job timed out after {CRON_JOB_TIMEOUT_S}s. "
                "Tool calls may be queued or blocked (e.g. permissions)."
            )
        if job.payload.deliver and job.payload.to:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or "",
            ))
        return response

    cron.on_job = on_cron_job

    # Register default memory_sleep system_event job if enabled and none exists
    memory_sleep_cfg = getattr(config, "memory_sleep", None)
    if memory_sleep_cfg and getattr(memory_sleep_cfg, "enabled", True) and cron.get_system_job_by_name("memory_sleep") is None:
        schedule_expr = getattr(memory_sleep_cfg, "schedule", "0 2 * * *") or "0 2 * * *"
        cron.add_system_job(
            name="memory_sleep",
            schedule=CronSchedule(kind="cron", expr=schedule_expr),
        )

    kg_dedup_cfg = getattr(config, "kg_dedup", None)
    if kg_dedup_cfg and getattr(kg_dedup_cfg, "enabled", False) and cron.get_system_job_by_name("kg_dedup") is None:
        kg_schedule = getattr(kg_dedup_cfg, "schedule", "0 3 * * *") or "0 3 * * *"
        cron.add_system_job(
            name="kg_dedup",
            schedule=CronSchedule(kind="cron", expr=kg_schedule),
        )

    # Wire heartbeat callback (needs agent reference)
    async def on_execute(prompt: str) -> str:
        return await agent.process_direct(prompt, session_key="heartbeat")

    hb_cfg = getattr(config.gateway, "heartbeat", None)
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        provider=provider,
        model=config.agents.defaults.model,
        on_execute=on_execute,
        interval_s=hb_cfg.interval_s if hb_cfg else 30 * 60,
        enabled=hb_cfg.enabled if hb_cfg else True,
    )

    channels = ChannelManager(config, bus)

    if channels.enabled_channels:
        logger.info(f"Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        logger.warning("No chat channels enabled (configure in ~/.nanobot/config.json)")

    return config, bus, agent, session_manager, channels, cron, heartbeat
