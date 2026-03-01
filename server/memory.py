"""
Immediate memory step for the web client.

After each web reply, an optional fast model analyzes the last exchange
against current MEMORY.md and may append to HISTORY.md and/or update MEMORY.md.
Runs fire-and-forget so it never blocks the WebSocket response.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import json_repair
from litellm import acompletion
from loguru import logger

from nanobot.agent.memory import MemoryStore
from nanobot.providers.litellm_provider import resolve_model

if TYPE_CHECKING:
    from nanobot.config.schema import Config


async def run_immediate_memory(
    workspace_path: Path,
    config: "Config",
    last_messages: list[dict[str, Any]],
) -> None:
    """
    Analyze the last exchange with reference to current MEMORY.md; optionally
    append to HISTORY.md and/or update MEMORY.md. Uses the configured
    memory_model (e.g. Groq). Swallows all errors so chat is never affected.
    """
    memory_model = (getattr(config.agents.defaults, "memory_model", None) or "").strip()
    if not memory_model:
        return

    try:
        memory = MemoryStore(workspace_path)
        current_memory = memory.read_long_term()

        lines = []
        for m in last_messages:
            if not m.get("content"):
                continue
            role = m.get("role", "unknown").upper()
            tools = ""
            if m.get("tools_used"):
                tools = f" [tools: {', '.join(m['tools_used'])}]"
            ts = (m.get("timestamp") or "")[:16] if m.get("timestamp") else "?"
            lines.append(f"[{ts}] {role}{tools}: {m['content']}")
        conversation = "\n".join(lines) if lines else "(no content)"

        prompt = f"""You are a memory consolidation agent. Look at the current long-term memory and this single conversation turn. Decide if anything should be written to memory or history.

Return a JSON object with exactly these keys:
1. "needs_write": boolean — true only if something from this turn is worth persisting (new fact, preference, decision, or notable event).
2. "history_entry": string or null — If needs_write is true, a short paragraph (2-5 sentences) summarizing this turn for HISTORY.md. Start with a timestamp like [YYYY-MM-DD HH:MM]. Otherwise null.
3. "memory_update": string or null — If needs_write is true and there are new long-term facts (user info, preferences, project context, technical decisions), the FULL updated MEMORY.md content (merge new with existing). If nothing to add, null. If null, existing memory is left unchanged.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation turn to process
{conversation}

Respond with ONLY valid JSON, no markdown fences."""

        provider_name = config.get_provider_name(memory_model)
        p = config.get_provider(memory_model)
        api_key = p.api_key if p else None
        api_base = config.get_api_base(memory_model)
        extra_headers = p.extra_headers if p else None
        resolved_model = resolve_model(
            memory_model,
            provider_name=provider_name,
            api_key=api_key,
            api_base=api_base,
        )

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": "You are a memory consolidation agent. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.2,
            "stream": False,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base
        if extra_headers:
            kwargs["extra_headers"] = extra_headers

        response = await acompletion(**kwargs)
        text = ""
        if response.choices and response.choices[0].message and response.choices[0].message.content:
            text = (response.choices[0].message.content or "").strip()
        if not text:
            logger.debug("Immediate memory: empty response, skipping")
            return
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        result = json_repair.loads(text)
        if not isinstance(result, dict):
            logger.warning(f"Immediate memory: unexpected response type. Response: {text[:200]}")
            return
        if not result.get("needs_write"):
            return
        entry = result.get("history_entry")
        if entry and isinstance(entry, str) and entry.strip():
            memory.append_history(entry.strip())
            logger.debug("Immediate memory: appended history entry")
        update = result.get("memory_update")
        if update is not None and isinstance(update, str) and update.strip() != current_memory:
            memory.write_long_term(update.strip())
            logger.debug("Immediate memory: updated MEMORY.md")
    except Exception as e:
        logger.warning(f"Immediate memory failed (non-fatal): {e}")
