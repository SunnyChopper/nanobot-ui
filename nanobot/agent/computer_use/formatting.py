"""
Format Action or action-summary dicts for logs, prompts, and hints.

Action summary contract: a dict with required "kind"; optional "x", "y", "key", "text", "extra".
Producers (e.g. tool's _action_summary) should set "extra" for kinds that need it (e.g. drag_and_drop
with destination_x, destination_y).
"""

from __future__ import annotations

from typing import Any, Literal

from nanobot.agent.computer_use.base import Action


def format_action(
    action_or_summary: Action | dict[str, Any],
    *,
    style: Literal["log"] | Literal["prompt"] | Literal["hint"] = "log",
    max_len: int | None = None,
) -> str:
    """Format a single Action or action-summary dict for display.

    - style="log": one-line for debug (e.g. click(240, 150), key(win+r)). No truncation unless max_len set.
    - style="prompt": same as log; use max_len (e.g. 40) for "do NOT repeat" lines.
    - style="hint": short label for hint lists (key/text truncated to ~20 chars).
    """
    if isinstance(action_or_summary, Action):
        kind = action_or_summary.kind
        x, y = action_or_summary.x, action_or_summary.y
        key = action_or_summary.key or ""
        text = action_or_summary.text or ""
        extra = action_or_summary.extra or {}
    else:
        a = action_or_summary
        kind = (a.get("kind") or "?").strip()
        x, y = a.get("x"), a.get("y")
        key = a.get("key") or ""
        text = a.get("text") or ""
        extra = a.get("extra") or {}

    if x is not None and y is not None:
        if kind == "drag_and_drop":
            dx = extra.get("destination_x")
            dy = extra.get("destination_y")
            if dx is not None and dy is not None:
                part = f"{kind}({x},{y})->({dx},{dy})"
            else:
                part = f"{kind}({x},{y})"
        else:
            part = f"{kind}({x},{y})"
    elif key:
        part = f"{kind}({key})"
    elif text:
        part = f"{kind}({text!r})"
    else:
        part = kind

    if style == "hint":
        part = part[:20] + ("…" if len(part) > 20 else "")
    if max_len is not None and len(part) > max_len:
        part = part[:max_len] + "…"
    return part


def format_action_list(
    summaries: list[dict[str, Any]],
    *,
    max_items: int = 10,
    style: Literal["hint"] = "hint",
) -> str:
    """Format a list of action-summary dicts to a comma-separated string for hints and "Exact screen match" lines."""
    if not summaries:
        return ""
    parts = [
        format_action(s, style=style)
        for s in summaries[:max_items]
    ]
    return ", ".join(parts)
