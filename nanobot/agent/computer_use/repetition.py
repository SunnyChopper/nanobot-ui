"""Repetition detection for computer use: identical/near-identical action summaries and last repeated count."""

from __future__ import annotations

from typing import Any

# Two positional actions (click, hover_at, etc.) within this many pixels are treated as the same for repeat detection.
DEFAULT_REPEAT_PIXEL_TOLERANCE = 10

# Kinds that have (x, y) and should use pixel tolerance for "same action".
_POSITIONAL_KINDS = frozenset({"click", "hover_at", "type_text_at", "drag_and_drop", "scroll_at"})


def action_summaries_identical(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Return True if two action summary dicts represent the same action (same kind and key params)."""
    if (a.get("kind") or "") != (b.get("kind") or ""):
        return False
    ax, ay = a.get("x"), a.get("y")
    bx, by = b.get("x"), b.get("y")
    if ax is not None and ay is not None and bx is not None and by is not None:
        return ax == bx and ay == by
    if a.get("key") or b.get("key"):
        return (a.get("key") or "") == (b.get("key") or "")
    if a.get("text") is not None or b.get("text") is not None:
        return (a.get("text") or "") == (b.get("text") or "")
    return True


def action_summaries_nearly_identical(
    a: dict[str, Any],
    b: dict[str, Any],
    *,
    pixel_tolerance: int = DEFAULT_REPEAT_PIXEL_TOLERANCE,
) -> bool:
    """Return True if two action summaries represent the same or nearly same action.

    For positional kinds (click, hover_at, type_text_at, drag_and_drop, scroll_at), coordinates
    within pixel_tolerance are treated as the same. For other kinds, uses exact match.
    """
    if (a.get("kind") or "") != (b.get("kind") or ""):
        return False
    kind = (a.get("kind") or "").strip()
    if kind in _POSITIONAL_KINDS:
        ax, ay = a.get("x"), a.get("y")
        bx, by = b.get("x"), b.get("y")
        if ax is None or ay is None or bx is None or by is None:
            return ax == bx and ay == by
        if abs(ax - bx) > pixel_tolerance or abs(ay - by) > pixel_tolerance:
            return False
        if kind == "drag_and_drop":
            extra_a = a.get("extra") or {}
            extra_b = b.get("extra") or {}
            dx_a, dy_a = extra_a.get("destination_x"), extra_a.get("destination_y")
            dx_b, dy_b = extra_b.get("destination_x"), extra_b.get("destination_y")
            if dx_a is not None and dy_a is not None and dx_b is not None and dy_b is not None:
                if abs(dx_a - dx_b) > pixel_tolerance or abs(dy_a - dy_b) > pixel_tolerance:
                    return False
        return True
    return action_summaries_identical(a, b)


def last_repeated_action_count(
    actions: list[dict[str, Any]],
    *,
    pixel_tolerance: int = DEFAULT_REPEAT_PIXEL_TOLERANCE,
) -> tuple[int, dict[str, Any] | None]:
    """Return (count, last_action) for how many of the last actions are identical or nearly identical (1 = no repeat).

    When pixel_tolerance > 0, positional actions (click, hover_at, etc.) within that many pixels
    count as the same. When pixel_tolerance is 0, only exact matches count.
    """
    if not actions:
        return 0, None
    last = actions[-1]
    count = 1
    for i in range(len(actions) - 2, -1, -1):
        if pixel_tolerance > 0:
            same = action_summaries_nearly_identical(actions[i], last, pixel_tolerance=pixel_tolerance)
        else:
            same = action_summaries_identical(actions[i], last)
        if same:
            count += 1
        else:
            break
    return count, last


def last_same_kind_streak(actions: list[dict[str, Any]]) -> tuple[int, str | None]:
    """Return (count, kind) for how many of the last actions share the same kind (0 = empty list)."""
    if not actions:
        return 0, None
    last_kind = (actions[-1].get("kind") or "").strip()
    if not last_kind:
        return 0, None
    count = 1
    for i in range(len(actions) - 2, -1, -1):
        if (actions[i].get("kind") or "").strip() == last_kind:
            count += 1
        else:
            break
    return count, last_kind


# Pixel tolerance for "similar" in oscillation (A-B-A-B); looser than repeat detection.
_OSCILLATION_PIXEL_TOLERANCE = 50


def detect_oscillation(
    actions: list[dict[str, Any]],
    window: int = 6,
    *,
    pixel_tolerance: int = _OSCILLATION_PIXEL_TOLERANCE,
) -> bool:
    """Return True if the last actions alternate between two similar actions (A-B-A-B or A-B-A-B-A-B).

    Used to detect e.g. clicking the same dropdown open/close. Same kind + coordinates within
    pixel_tolerance count as the same "slot". Requires at least 4 actions in window.
    """
    if window < 4 or len(actions) < 4:
        return False
    recent = actions[-window:]
    # Even-indexed (0,2,4...) should be same slot; odd (1,3,5...) same slot; and the two slots differ.
    def same_slot(i: int, j: int) -> bool:
        ai, aj = recent[i], recent[j]
        if (ai.get("kind") or "") != (aj.get("kind") or ""):
            return False
        return action_summaries_nearly_identical(ai, aj, pixel_tolerance=pixel_tolerance)
    n = len(recent)
    # Check alternating: 0,2,4... same; 1,3,5... same; slot0 != slot1
    if not same_slot(0, 2):
        return False
    if n < 4 or not same_slot(1, 3):
        return False
    if same_slot(0, 1):
        return False
    if n >= 5 and (not same_slot(0, 4) or not same_slot(2, 4)):
        return False
    if n >= 6 and (not same_slot(1, 5) or not same_slot(3, 5)):
        return False
    return True
