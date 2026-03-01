"""
FastAPI application factory for the nanobot web server.

Creates the ASGI app, mounts REST routes and WebSocket endpoint, starts
all nanobot services inside the lifespan context, and optionally serves
the React build from frontend/dist/.

Usage:
    from server.app import create_app
    app = create_app(config, bus, agent, session_manager, channels, cron, heartbeat)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.config.loader import get_data_dir
from server.agents.registry import build_workflow_summary
from server.routes import router
from server.services import NanobotSessionService
from server.channels import WebChannel
from server.websocket import ConnectionRegistry, websocket_endpoint

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop
    from nanobot.channels.manager import ChannelManager
    from nanobot.config.schema import Config
    from nanobot.cron.service import CronService
    from nanobot.heartbeat.service import HeartbeatService
    from nanobot.session.manager import SessionManager


def create_app(
    config: "Config",
    bus: Any,
    agent: "AgentLoop",
    session_manager: "SessionManager",
    channels: "ChannelManager",
    cron: "CronService",
    heartbeat: "HeartbeatService",
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    All nanobot services are started inside the lifespan context so they
    share the same asyncio event loop as the ASGI server (uvicorn).
    """

    # Build a ContextBuilder and ToolRegistry that the WebSocket handler
    # can use for the streaming agent loop. Use same options as CLI/bus path:
    # workspace, mcp_guidance. Optionally set workflow_summary_callback below.
    context_builder = ContextBuilder(
        config.workspace_path,
        mcp_guidance=config.tools.mcp_guidance,
        system_prompt_max_chars=getattr(config.agents.defaults, "system_prompt_max_chars", 0) or 0,
        memory_section_max_chars=getattr(config.agents.defaults, "memory_section_max_chars", 0) or 0,
        section_order=getattr(config.agents.defaults, "system_prompt_section_order", None) or None,
        history_max_chars=getattr(config.agents.defaults, "history_max_chars", 0) or 0,
    )
    data_dir = get_data_dir()
    context_builder.workflow_summary_callback = lambda: build_workflow_summary(data_dir)
    # Reuse the agent's tool registry (read-only from the server's perspective)
    tool_registry: ToolRegistry = agent.tools

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Start nanobot services; stop them on shutdown."""
        logger.info("Nanobot web server starting up...")

        # Start background services
        await cron.start()
        await heartbeat.start()

        # Start agent loop and channel manager as concurrent background tasks
        background_tasks = [
            asyncio.create_task(agent.run(), name="agent_loop"),
            asyncio.create_task(channels.start_all(), name="channel_manager"),
        ]

        logger.info(
            f"Nanobot web server ready on "
            f"http://{config.gateway.host}:{config.gateway.port}"
        )

        yield  # Server is running

        logger.info("Nanobot web server shutting down...")
        agent.stop()
        heartbeat.stop()
        cron.stop()
        await channels.stop_all()
        await agent.close_mcp()

        for task in background_tasks:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    # -----------------------------------------------------------------------
    # App creation
    # -----------------------------------------------------------------------
    app = FastAPI(
        title="nanobot",
        description="Personal AI assistant - web API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS -- allow the Vite dev server (localhost:5173) during development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            # In production everything is served from the same origin
            f"http://{config.gateway.host}:{config.gateway.port}",
            f"http://localhost:{config.gateway.port}",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store references for route handlers (injected via request.app.state)
    app.state.config = config
    app.state.session_manager = session_manager
    app.state.session_service = NanobotSessionService(session_manager)
    app.state.context_builder = context_builder
    app.state.tool_registry = tool_registry
    app.state.agent = agent
    app.state.channels = channels
    app.state.cron = cron
    app.state.kg_dedup_runs = {}  # run_id -> queue.Queue for SSE progress

    # REST routes under /api
    app.include_router(router, prefix="/api")

    # WebSocket connection registry and web outbound channel (subagent callbacks, etc.)
    ws_registry = ConnectionRegistry()
    app.state.ws_registry = ws_registry
    channels.register_channel("web", WebChannel(ws_registry))

    @app.websocket("/ws/chat")
    async def ws_chat(ws: WebSocket) -> None:
        await websocket_endpoint(
            ws=ws,
            registry=ws_registry,
            session_manager=session_manager,
            context_builder=context_builder,
            tool_registry=tool_registry,
            config=config,
            agent=agent,
        )

    # -----------------------------------------------------------------------
    # Static files (React build) -- mounted LAST so API routes take priority
    # -----------------------------------------------------------------------
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dist), html=True),
            name="frontend",
        )
        logger.info(f"Serving React build from {frontend_dist}")
    else:
        logger.info(
            "frontend/dist/ not found -- run 'npm run build' inside frontend/ "
            "to enable production serving. Dev server: npm run dev"
        )

    return app
