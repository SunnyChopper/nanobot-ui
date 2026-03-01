"""Screen capture for computer use. Phase 1: pyautogui; Phase 2 can add mss."""

from __future__ import annotations

from io import BytesIO

import pyautogui

from nanobot.utils.helpers import ensure_windows_dpi_aware


def capture_screen_png() -> bytes:
    """Capture the primary screen as PNG bytes using pyautogui. Use for Phase 1."""
    ensure_windows_dpi_aware()
    im = pyautogui.screenshot()
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
