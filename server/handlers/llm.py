"""LLM-related HTTP handlers: profiler (test connection, stream metrics)."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import Request
from litellm import acompletion

from nanobot.providers.litellm_provider import resolve_model
from server.models import LlmProfilerResponse


async def post_llm_profiler(request: Request) -> LlmProfilerResponse:
    """
    Run a minimal streaming completion and return connection and stream metrics.

    Uses the current in-memory config (same model/credentials as WebSocket chat).
    """
    config = request.app.state.config
    raw_model = (config.agents.defaults.model or "").strip()
    if not raw_model:
        raw_model = "anthropic/claude-opus-4-5"
    provider_name = config.get_provider_name(raw_model)
    p = config.get_provider(raw_model)
    api_key = p.api_key if p else None
    api_base = config.get_api_base(raw_model)
    extra_headers = p.extra_headers if p else None
    model = resolve_model(
        raw_model, provider_name=provider_name, api_key=api_key, api_base=api_base
    )

    if model.startswith("gemini/") and api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 10,
        "temperature": 0,
        "stream": True,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
    if extra_headers:
        kwargs["extra_headers"] = extra_headers

    start = time.perf_counter()
    first_token_at: float | None = None
    content_chars = 0
    has_thinking = False

    try:
        stream = await acompletion(**kwargs)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                has_thinking = True
                if first_token_at is None:
                    first_token_at = time.perf_counter()
            if delta.content:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                content_chars += len(delta.content or "")
        end = time.perf_counter()

        if first_token_at is None:
            first_token_at = end
        time_to_first_ms = int((first_token_at - start) * 1000)
        duration_s = end - first_token_at
        tokens_per_second: float | None = None
        if duration_s > 0 and content_chars > 0:
            tokens_per_second = (content_chars / 4.0) / duration_s

        return LlmProfilerResponse(
            ok=True,
            error=None,
            time_to_first_token_ms=time_to_first_ms,
            tokens_per_second=tokens_per_second,
            has_thinking_stream=has_thinking,
        )
    except Exception as e:
        return LlmProfilerResponse(
            ok=False,
            error=str(e),
            time_to_first_token_ms=None,
            tokens_per_second=None,
            has_thinking_stream=False,
        )
