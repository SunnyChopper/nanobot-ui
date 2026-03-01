"""Webhook HTTP handler: trigger agent with a message from external services."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import Header, HTTPException, Request

from server.models import WebhookTriggerRequest


def _get_webhook_token(
    request: Request, x_webhook_token: str | None = None
) -> str | None:
    """Extract webhook token from header or Authorization Bearer."""
    if x_webhook_token:
        return x_webhook_token
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


async def webhook_trigger(
    request: Request,
    body: WebhookTriggerRequest,
    x_webhook_token: str | None = Header(None, alias="X-Webhook-Token"),
) -> dict:
    """
    Trigger the agent with a message (e.g. from GitHub, IFTTT).
    Requires gateway.webhook_secret. Returns 202 with job_id (session key).
    """
    from loguru import logger
    from nanobot.providers.litellm_provider import ensure_provider_env, resolve_model
    from server.models import StreamAgentLoopParams
    from server.services.streaming import stream_agent_loop

    config = request.app.state.config
    secret = getattr(config.gateway, "webhook_secret", None) or ""
    if not secret:
        raise HTTPException(
            status_code=501,
            detail="Webhook not configured (set gateway.webhook_secret)",
        )
    token = _get_webhook_token(request, x_webhook_token)
    if not token or token != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook token")

    content = (body.message or body.prompt or "").strip()
    if not content:
        raise HTTPException(
            status_code=400, detail="Body must include 'message' or 'prompt'"
        )

    sm = request.app.state.session_manager
    context_builder = request.app.state.context_builder
    tool_registry = request.app.state.tool_registry

    session_key = f"web:webhook-{uuid.uuid4().hex[:12]}"
    session = sm.get_or_create(session_key)
    session.add_message("user", content)

    raw_model = (
        (config.agents.defaults.model or "").strip()
        or "anthropic/claude-opus-4-5"
    )
    provider_name = config.get_provider_name(raw_model)
    p = config.get_provider(raw_model)
    api_key = p.api_key if p else None
    api_base = config.get_api_base(raw_model)
    extra_headers = p.extra_headers if p else None
    model = resolve_model(
        raw_model,
        provider_name=provider_name,
        api_key=api_key,
        api_base=api_base,
    )
    ensure_provider_env(model, provider_name, api_key, api_base)

    async def no_op_event(_: dict) -> None:
        pass

    async def deny_approval(_name: str, _args: dict, _tid: str) -> bool:
        return False

    async def run_webhook_agent() -> None:
        try:
            params = StreamAgentLoopParams(
                context_builder=context_builder,
                session=session,
                tool_registry=tool_registry,
                model=model,
                temperature=config.agents.defaults.temperature,
                max_tokens=config.agents.defaults.max_tokens,
                max_iterations=config.agents.defaults.max_tool_iterations,
                memory_window=config.agents.defaults.memory_window,
                user_message=content,
                on_event=no_op_event,
                channel="webhook",
                chat_id=session_key,
                api_key=api_key,
                api_base=api_base,
                extra_headers=extra_headers,
                tool_policy=dict(config.tools.tool_policy),
                request_approval=deny_approval,
                max_llm_retries=getattr(
                    config.agents.defaults, "max_llm_retries", 3
                ),
                retry_backoff_base_seconds=getattr(
                    config.agents.defaults, "retry_backoff_base_seconds", 2
                ),
                circuit_breaker_failure_threshold=getattr(
                    config.gateway, "circuit_breaker_failure_threshold", 5
                ),
                circuit_breaker_recovery_seconds=getattr(
                    config.gateway, "circuit_breaker_recovery_seconds", 60.0
                ),
                tool_timeout_seconds=getattr(config.tools, "tool_timeout_seconds", 0) or 0,
                cua_auto_approve=getattr(config.tools, "cua_auto_approve", False),
                cua_safety_model=getattr(config.tools, "cua_safety_model", "") or "llama-3.1-8b-instant",
                cua_safety_api_key=getattr(getattr(config.providers, "groq", None), "api_key", None) or None,
            )
            result = await stream_agent_loop(params)
            session.add_message(
                "assistant",
                result.final_content or "(no response)",
                tools_used=result.tools_used if result.tools_used else None,
            )
            if not session.metadata.get("title"):
                session.metadata["title"] = (
                    content[:60].strip() + ("…" if len(content) > 60 else "")
                )
            sm.save(session)
        except Exception as exc:
            logger.error(f"Webhook agent error for {session_key}: {exc}")

    asyncio.create_task(run_webhook_agent())
    return {"status": "accepted", "job_id": session_key}
