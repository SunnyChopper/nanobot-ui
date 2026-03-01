"""
AI-assisted memory tasks: verify bullet, scan irrelevant history.
Uses single LLM calls with strict JSON output; no tool use.
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

# HISTORY.md entries are separated by double newline (see MemoryStore.append_history).
HISTORY_ENTRY_SEP = "\n\n"


async def _call_llm(
    config: "Config",
    prompt: str,
    system: str,
    model_key: str = "memory_model",
) -> str | None:
    """Call LLM; returns response text or None on failure."""
    model = (
        getattr(config.agents.defaults, model_key, None) or config.agents.defaults.model or ""
    ).strip()
    if not model:
        logger.warning("Memory tasks: no model configured")
        return None
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)
    api_key = p.api_key if p else None
    api_base = config.get_api_base(model)
    extra_headers = p.extra_headers if p else None
    resolved = resolve_model(
        model, provider_name=provider_name, api_key=api_key, api_base=api_base
    )
    kwargs: dict[str, Any] = {
        "model": resolved,
        "messages": [
            {"role": "system", "content": system},
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
    try:
        response = await acompletion(**kwargs)
        if (
            response.choices
            and response.choices[0].message
            and response.choices[0].message.content
        ):
            return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"Memory tasks LLM call failed: {e}")
    return None


def _parse_json_response(text: str) -> dict[str, Any] | None:
    """Strip markdown code fences if present and parse JSON."""
    if not text or not text.strip():
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json_repair.loads(t)
    except Exception:
        return None


async def run_verify_bullet(
    workspace_path: Path, config: "Config", text: str
) -> dict[str, Any]:
    """
    Ask LLM whether the given bullet/fact is still accurate.
    Returns {"verified": bool, "comment": str}. On failure returns verified=False, comment=error.
    """
    workspace_path = Path(workspace_path).resolve()
    memory = MemoryStore(workspace_path)
    current_memory = memory.read_long_term() or "(empty)"
    prompt = f"""Consider this long-term memory context and the following claim.

## Current long-term memory (MEMORY.md)
{current_memory[:8000]}

## Claim to verify
{text}

Is this claim still accurate given the memory above? Reply with ONLY a JSON object with two keys:
- "verified": true or false
- "comment": a brief reason (one sentence)"""
    system = "You are a fact-checking agent. Respond only with valid JSON. No markdown, no explanation."
    response = await _call_llm(config, prompt, system)
    if not response:
        return {"verified": False, "comment": "LLM call failed or no model configured."}
    parsed = _parse_json_response(response)
    if not parsed or not isinstance(parsed, dict):
        return {"verified": False, "comment": "Could not parse LLM response as JSON."}
    verified = bool(parsed.get("verified", False))
    comment = str(parsed.get("comment", "")).strip() or "No comment."
    return {"verified": verified, "comment": comment}


async def run_scan_irrelevant_history(
    workspace_path: Path, config: "Config"
) -> dict[str, Any]:
    """
    Ask LLM to identify HISTORY.md entries that seem irrelevant or redundant.
    Returns {"irrelevant_indices": [0, 2, ...], "reasons": {0: "...", 2: "..."}}.
    Entries are 0-based; splitting uses \\n\\n.
    """
    workspace_path = Path(workspace_path).resolve()
    memory = MemoryStore(workspace_path)
    history = memory.read_history() or ""
    entries = [e.strip() for e in history.split(HISTORY_ENTRY_SEP) if e.strip()]
    if not entries:
        return {"irrelevant_indices": [], "reasons": {}}
    # Send first N entries to stay under context
    sample = "\n\n---ENTRY---\n\n".join(
        f"[{i}] {entries[i]}" for i in range(min(len(entries), 80))
    )
    prompt = f"""Below are numbered entries from a history log (one entry per [index] block).
Which entries seem irrelevant, redundant, or no longer useful? Reply with ONLY a JSON object with two keys:
- "irrelevant_indices": array of 0-based indices, e.g. [0, 2, 5]
- "reasons": object mapping each index (as string key) to a single brief sentence explaining why that entry can be removed, e.g. {{ "0": "One-off task already completed.", "2": "Redundant with entry 1." }}

Use 0-based indices. Return an empty array for irrelevant_indices if none are irrelevant. Do not include indices beyond the list. Provide a reason for every index you list.

Entries:
{sample}"""
    system = "You output only valid JSON with keys 'irrelevant_indices' (array of integers) and 'reasons' (object: index string -> one sentence). No markdown."
    response = await _call_llm(config, prompt, system)
    if not response:
        return {"irrelevant_indices": [], "reasons": {}}
    parsed = _parse_json_response(response)
    if not parsed or not isinstance(parsed, dict):
        return {"irrelevant_indices": [], "reasons": {}}
    raw = parsed.get("irrelevant_indices")
    if not isinstance(raw, list):
        return {"irrelevant_indices": [], "reasons": {}}
    indices = []
    for x in raw:
        try:
            if isinstance(x, int) and not isinstance(x, bool):
                indices.append(x)
            elif isinstance(x, (float, str)):
                indices.append(int(float(x)))
        except (ValueError, TypeError):
            pass
    n = len(entries)
    indices = sorted(set(i for i in indices if 0 <= i < n))
    # Parse reasons: {"0": "...", "2": "..."} or {"0": "...", 2: "..."}
    reasons_raw = parsed.get("reasons")
    reasons: dict[int, str] = {}
    if isinstance(reasons_raw, dict):
        for i in indices:
            val = reasons_raw.get(i) or reasons_raw.get(str(i))
            if isinstance(val, str) and val.strip():
                reasons[i] = val.strip()
    return {"irrelevant_indices": indices, "reasons": reasons}


def remove_history_entries(workspace_path: Path, indices: list[int]) -> int:
    """
    Remove HISTORY.md entries by 0-based index. Entries are split by double newline.
    Returns the number of entries removed.
    """
    workspace_path = Path(workspace_path).resolve()
    memory = MemoryStore(workspace_path)
    history = memory.read_history() or ""
    entries = [e.strip() for e in history.split(HISTORY_ENTRY_SEP) if e.strip()]
    to_remove = sorted(set(i for i in indices if 0 <= i < len(entries)))
    if not to_remove:
        return 0
    new_entries = [e for i, e in enumerate(entries) if i not in to_remove]
    new_content = HISTORY_ENTRY_SEP.join(new_entries)
    if new_entries:
        new_content = new_content.rstrip() + "\n"
    memory.history_file.write_text(new_content, encoding="utf-8")
    return len(to_remove)
