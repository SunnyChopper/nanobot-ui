"""Config and status HTTP handlers: status, channels, providers, models, config get/patch."""

from __future__ import annotations

from fastapi import Request
from nanobot import __version__
from nanobot.config.loader import save_config
from nanobot.config.schema import KgDedupConfig, MCPServerConfig
from nanobot.providers.registry import find_by_name

from server.constants import DEFAULT_TOOL_POLICY, PROVIDER_MODELS
from server.models import (
    AgentConfigResponse,
    ChannelStatusItem,
    ChannelsResponse,
    ConfigPatch,
    ConfigResponse,
    KgDedupConfigResponse,
    MCPServerConfigResponse,
    ModelOption,
    ModelsResponse,
    ProviderConfigResponse,
    ProviderItem,
    ProvidersResponse,
    StatusResponse,
    ToolsConfigResponse,
)


async def get_status(request: Request) -> StatusResponse:
    """Return backend health and configuration summary."""
    config = request.app.state.config
    channels = request.app.state.channels
    return StatusResponse(
        version=__version__,
        model=config.agents.defaults.model,
        workspace=str(config.workspace_path),
        channels_enabled=channels.enabled_channels,
    )


async def get_channels(request: Request) -> ChannelsResponse:
    """Return the status of all enabled chat channels."""
    channels = request.app.state.channels
    status = channels.get_status()
    items = [
        ChannelStatusItem(
            name=name,
            enabled=info.get("enabled", True),
            running=info.get("running", False),
        )
        for name, info in status.items()
    ]
    return ChannelsResponse(channels=items)


async def get_providers(request: Request) -> ProvidersResponse:
    """Return list of LLM providers with display names and API key status."""
    from nanobot.providers.registry import PROVIDERS

    config = request.app.state.config
    items: list[ProviderItem] = []
    for spec in PROVIDERS:
        p = getattr(config.providers, spec.name, None)
        if p is None:
            continue
        has_key = bool(spec.is_oauth or (p and p.api_key))
        items.append(
            ProviderItem(
                id=spec.name,
                display_name=spec.label or spec.name.title(),
                has_api_key=has_key,
            )
        )
    return ProvidersResponse(providers=items)


async def get_models(request: Request) -> ModelsResponse:
    """Return available models based on which providers have API keys."""
    config = request.app.state.config
    current = (config.agents.defaults.model or "").strip()
    current_provider = config.get_provider_name(current) if current else None

    seen: set[str] = set()
    options: list[ModelOption] = []

    def add(model_id: str, label: str, provider: str) -> None:
        if model_id not in seen:
            seen.add(model_id)
            options.append(ModelOption(id=model_id, label=label, provider=provider))

    if current:
        add(current, current, current_provider or "custom")

    for spec_name, model_list in PROVIDER_MODELS.items():
        spec = find_by_name(spec_name)
        p = getattr(config.providers, spec_name, None)
        if p is None:
            continue
        if spec and spec.is_oauth:
            pass
        elif not (p and p.api_key):
            continue
        for model_id, label in model_list:
            add(model_id, label, spec_name)

    return ModelsResponse(models=options, current=current or "")


async def get_config(request: Request, auth_user: object) -> ConfigResponse:
    """Return a safe subset of the nanobot config (no raw API keys)."""
    config = request.app.state.config
    d = config.agents.defaults

    mcp = {
        name: MCPServerConfigResponse(
            command=srv.command,
            args=srv.args,
            env=srv.env,
            url=srv.url,
        )
        for name, srv in config.tools.mcp_servers.items()
    }

    effective_policy = {**DEFAULT_TOOL_POLICY, **config.tools.tool_policy}

    providers_safe: dict[str, ProviderConfigResponse] = {}
    for name, p in config.providers.model_dump().items():
        providers_safe[name] = ProviderConfigResponse(
            api_key_set=bool(p.get("api_key")),
            api_base=p.get("api_base"),
        )

    kg_dedup_cfg = getattr(config, "kg_dedup", None)
    kg_dedup = (
        KgDedupConfigResponse(
            enabled=getattr(kg_dedup_cfg, "enabled", False),
            schedule=getattr(kg_dedup_cfg, "schedule", "0 3 * * *") or "0 3 * * *",
            kg_dedup_model=getattr(kg_dedup_cfg, "kg_dedup_model", "") or "",
            llm_batch_size=getattr(kg_dedup_cfg, "llm_batch_size", 20),
            batch_size=getattr(kg_dedup_cfg, "batch_size", 256),
        )
        if kg_dedup_cfg
        else KgDedupConfigResponse()
    )

    return ConfigResponse(
        agent=AgentConfigResponse(
            model=d.model,
            max_tokens=d.max_tokens,
            temperature=d.temperature,
            max_tool_iterations=d.max_tool_iterations,
            memory_window=d.memory_window,
            workspace=d.workspace,
        ),
        tools=ToolsConfigResponse(
            restrict_to_workspace=config.tools.restrict_to_workspace,
            exec_timeout=config.tools.exec.timeout,
            web_search_api_key_set=bool(config.tools.web.search.api_key),
            tool_policy=effective_policy,
            mcp_guidance=getattr(config.tools, "mcp_guidance", None) or {},
            cua_auto_approve=getattr(config.tools, "cua_auto_approve", False),
            cua_safety_model=getattr(config.tools, "cua_safety_model", "") or "llama-3.1-8b-instant",
        ),
        kg_dedup=kg_dedup,
        mcp_servers=mcp,
        providers=providers_safe,
        workspace=str(config.workspace_path),
        version=__version__,
    )


async def patch_config(
    body: ConfigPatch, request: Request, auth_user: object
) -> dict:
    """Update writable config fields and persist to ~/.nanobot/config.json."""
    config = request.app.state.config

    if body.agent:
        d = config.agents.defaults
        if body.agent.model is not None:
            d.model = body.agent.model
        if body.agent.max_tokens is not None:
            d.max_tokens = body.agent.max_tokens
        if body.agent.temperature is not None:
            d.temperature = body.agent.temperature
        if body.agent.max_tool_iterations is not None:
            d.max_tool_iterations = body.agent.max_tool_iterations
        if body.agent.memory_window is not None:
            d.memory_window = body.agent.memory_window
        if body.agent.workspace is not None:
            d.workspace = body.agent.workspace

    if body.providers is not None:
        for name, patch in body.providers.items():
            p = getattr(config.providers, name, None)
            if p is None:
                continue
            if patch.api_key is not None:
                p.api_key = patch.api_key
            if patch.api_base is not None:
                p.api_base = patch.api_base if patch.api_base else None

    if body.restrict_to_workspace is not None:
        config.tools.restrict_to_workspace = body.restrict_to_workspace

    if body.exec_timeout is not None:
        config.tools.exec.timeout = body.exec_timeout

    if body.web_search_api_key is not None:
        config.tools.web.search.api_key = body.web_search_api_key

    if body.mcp_servers is not None:
        for name, srv_patch in body.mcp_servers.items():
            if srv_patch is None:
                config.tools.mcp_servers.pop(name, None)
            else:
                config.tools.mcp_servers[name] = MCPServerConfig(
                    command=srv_patch.command,
                    args=srv_patch.args,
                    env=srv_patch.env,
                    url=srv_patch.url,
                )

    if body.mcp_guidance is not None:
        config.tools.mcp_guidance = dict(body.mcp_guidance)

    if body.tool_policy is not None:
        config.tools.tool_policy.update(body.tool_policy)

    if body.cua_auto_approve is not None:
        config.tools.cua_auto_approve = body.cua_auto_approve
    if body.cua_safety_model is not None:
        config.tools.cua_safety_model = (body.cua_safety_model or "").strip() or "llama-3.1-8b-instant"

    # Sync run_python tool's skip-safety flag so it takes effect without server restart
    agent = getattr(request.app.state, "agent", None)
    if agent is not None:
        run_python_tool = agent.tools.get("run_python")
        if run_python_tool is not None and hasattr(run_python_tool, "_skip_safety_when_cua_auto"):
            run_python_tool._skip_safety_when_cua_auto = config.tools.cua_auto_approve

    if body.kg_dedup is not None:
        b = body.kg_dedup
        old_kg = getattr(config, "kg_dedup", None)
        enabled = (
            b.enabled
            if b.enabled is not None
            else (getattr(old_kg, "enabled", False))
        )
        schedule = (
            ((b.schedule or "").strip() or "0 3 * * *")
            if b.schedule is not None
            else (getattr(old_kg, "schedule", None) or "0 3 * * *")
        )
        kg_dedup_model = (
            (b.kg_dedup_model if b.kg_dedup_model is not None else getattr(old_kg, "kg_dedup_model", ""))
            or ""
        )
        llm_batch_size = (
            max(1, b.llm_batch_size)
            if b.llm_batch_size is not None
            else getattr(old_kg, "llm_batch_size", 20)
        )
        batch_size = (
            max(1, b.batch_size)
            if b.batch_size is not None
            else getattr(old_kg, "batch_size", 256)
        )
        config.kg_dedup = KgDedupConfig(
            enabled=enabled,
            schedule=schedule,
            kg_dedup_model=kg_dedup_model,
            llm_batch_size=llm_batch_size,
            batch_size=batch_size,
        )
        kg = config.kg_dedup
        cron = getattr(request.app.state, "cron", None)
        if cron is not None:
            from nanobot.cron.types import CronSchedule

            job = cron.get_system_job_by_name("kg_dedup")
            if kg.enabled and job is None:
                cron.add_system_job(
                    name="kg_dedup",
                    schedule=CronSchedule(kind="cron", expr=kg.schedule),
                )
            elif job is not None:
                if not kg.enabled:
                    cron.enable_job(job.id, False)
                else:
                    cron.update_schedule(
                        job.id, CronSchedule(kind="cron", expr=kg.schedule)
                    )

    save_config(config)
    return {"status": "saved"}
