"""
KG dedup LLM: clean I/O contract for batched merge decisions.
Uses litellm.acompletion; model from config (kg_dedup_model or memory_model).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import json_repair
from litellm import acompletion
from loguru import logger

from nanobot.providers.litellm_provider import resolve_model

if TYPE_CHECKING:
    from nanobot.config.schema import Config


def format_triple_phrase(subject: str, predicate: str, object: str) -> str:
    """Single canonical format for a triple when embedding or sending to the LLM."""
    return f"subject: {subject} | predicate: {predicate} | object: {object}"


@dataclass
class LlmDedupGroup:
    """One group sent to the LLM: target triple + up to 3 candidate triples (by cosine)."""

    group_id: int
    target: str
    candidates: list[str]
    target_idx: int
    candidate_indices: list[int]
    scores: list[float] | None = None


@dataclass
class LlmDedupDecision:
    """LLM output per group: which triple to keep (0=target, 1/2/3=candidates), which to remove."""

    group_id: int
    keep_index: int
    remove_indices: list[int]


def reindex_batch(groups: list[LlmDedupGroup]) -> list[LlmDedupGroup]:
    """Renumber group_id to 0..n-1 for a batch (for LLM input). Original indices stay in target_idx/candidate_indices."""
    return [
        LlmDedupGroup(
            group_id=i,
            target=g.target,
            candidates=g.candidates,
            target_idx=g.target_idx,
            candidate_indices=g.candidate_indices,
            scores=g.scores,
        )
        for i, g in enumerate(groups)
    ]


def apply_decisions_to_batch(
    batch: list[LlmDedupGroup],
    decisions: list[LlmDedupDecision],
) -> tuple[set[int], dict[int, int]]:
    """
    Map LLM decisions for one batch to global triple indices.
    Returns (indices_to_remove, canonical_of: removed_idx -> kept_idx).
    """
    to_remove: set[int] = set()
    canonical_of: dict[int, int] = {}
    for d in decisions:
        if d.group_id < 0 or d.group_id >= len(batch):
            continue
        g = batch[d.group_id]
        all_indices = [g.target_idx] + g.candidate_indices
        if d.keep_index < 0 or d.keep_index >= len(all_indices):
            continue
        canonical_idx = all_indices[d.keep_index]
        for ri in d.remove_indices:
            if ri == d.keep_index:
                continue
            if ri < 0 or ri >= len(all_indices):
                continue
            idx = all_indices[ri]
            to_remove.add(idx)
            canonical_of[idx] = canonical_idx
    return to_remove, canonical_of


def _parse_json_response(text: str) -> dict[str, Any] | None:
    if not text or not text.strip():
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json_repair.loads(t)
    except Exception:
        return None


def _build_prompt(groups: list[LlmDedupGroup]) -> str:
    lines = [
        "Each group below contains one target triple (index 0) and up to three candidate triples (indices 1,2,3). You must decide ONLY within that group: among these 4 (or fewer) triples, which say the same thing?",
        "",
        "SCOPE: For Group K, you may only look at the triples listed under '--- Group K ---'. Your decision for group_id K must only refer to indices 0,1,2,3 in that group. Do not cross-pollinate: do not merge or compare triples across different groups.",
        "",
        "WITHIN EACH GROUP: If two or more triples in the group express the same fact (duplicate or paraphrase), keep one (set keep_index to that index) and put the others in remove_indices. If none of the triples are duplicates — i.e. they all state different facts — then remove nothing: set remove_indices to [] and keep_index to 0.",
        "",
        "Output ONLY valid JSON: {\"decisions\": [{\"group_id\": <int>, \"keep_index\": <0-3>, \"remove_indices\": [<ints>]}, ...]}. One decision per group. remove_indices can be empty.",
        "",
    ]
    for g in groups:
        lines.append(f"--- Group {g.group_id} ---")
        lines.append(f"0 (target): {g.target}")
        for i, c in enumerate(g.candidates, 1):
            score_str = f" (cosine={g.scores[i-1]:.3f})" if g.scores and i - 1 < len(g.scores) else ""
            lines.append(f"{i}: {c}{score_str}")
        lines.append("")
    return "\n".join(lines)


async def ask_llm_merge_decisions(
    groups: list[LlmDedupGroup],
    config: "Config",
) -> list[LlmDedupDecision]:
    """
    Call the LLM once with all groups; parse structured response into decisions.
    Uses kg_dedup_model from config.kg_dedup if set, else memory_model.
    Returns only valid decisions; skips invalid entries with a warning.
    """
    if not groups:
        return []

    kg = getattr(config, "kg_dedup", None)
    model = (getattr(kg, "kg_dedup_model", None) or getattr(config.agents.defaults, "memory_model", None) or getattr(config.agents.defaults, "model", None) or "").strip()
    if not model:
        logger.warning("KG dedup LLM: no model configured (kg_dedup_model or memory_model)")
        return []

    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)
    api_key = p.api_key if p else None
    api_base = config.get_api_base(model)
    extra_headers = getattr(p, "extra_headers", None) if p else None
    resolved = resolve_model(
        model, provider_name=provider_name, api_key=api_key, api_base=api_base
    )
    kwargs: dict[str, Any] = {
        "model": resolved,
        "messages": [
            {"role": "system", "content": "You are a knowledge-graph deduplication agent. You work group by group: for each group, only the triples listed in that group exist for your decision. Within that group, only mark for removal triples that say the same thing as the one you keep (duplicate or paraphrase). Different facts in the same group must not be merged. When unsure, remove nothing (empty remove_indices). Output only valid JSON with key 'decisions'. No markdown, no explanation."},
            {"role": "user", "content": _build_prompt(groups)},
        ],
        "max_tokens": 4096,
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
        if not response.choices or not response.choices[0].message or not response.choices[0].message.content:
            return []
        text = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"KG dedup LLM call failed: {e}")
        return []

    parsed = _parse_json_response(text)
    if not parsed or not isinstance(parsed, dict):
        logger.warning("KG dedup LLM: could not parse response as JSON")
        return []

    raw = parsed.get("decisions")
    if not isinstance(raw, list):
        return []

    decisions: list[LlmDedupDecision] = []
    group_ids = {g.group_id for g in groups}
    for item in raw:
        if not isinstance(item, dict):
            continue
        gid = item.get("group_id")
        keep = item.get("keep_index")
        remove = item.get("remove_indices")
        if gid not in group_ids or not isinstance(keep, int) or keep not in (0, 1, 2, 3):
            continue
        if not isinstance(remove, list):
            remove = []
        remove = [int(x) for x in remove if isinstance(x, (int, float)) and 0 <= int(x) <= 3]
        decisions.append(LlmDedupDecision(group_id=int(gid), keep_index=keep, remove_indices=remove))
    return decisions
