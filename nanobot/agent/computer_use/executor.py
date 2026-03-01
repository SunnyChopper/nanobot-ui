"""Execute computer use Actions via pyautogui. Supports dry-run and optional confirm callback.

Implements all Gemini Computer Use supported actions per:
https://ai.google.dev/gemini-api/docs/computer-use#supported-actions
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from nanobot.agent.computer_use.base import Action
from nanobot.agent.computer_use.formatting import format_action
from nanobot.utils.helpers import ensure_windows_dpi_aware


def _check_pyautogui() -> str | None:
    try:
        ensure_windows_dpi_aware()
        import pyautogui  # noqa: F401
        return None
    except ImportError:
        return "Desktop automation not available: install pyautogui (pip install pyautogui)"


class ActionExecutor:
    """Executes Action items via pyautogui. Supports dry_run and optional confirm_callback."""

    def __init__(
        self,
        *,
        dry_run: bool = False,
        confirm_callback: Callable[[Action], Awaitable[bool]] | None = None,
    ):
        self.dry_run = dry_run
        self.confirm_callback = confirm_callback
        self._logged: list[str] = []

    def _execute_one(self, action: Action) -> str | None:
        """Execute one action. Returns unsupported kind name if not implemented, else None."""
        import time

        import pyautogui

        kind = action.kind.lower()
        if kind == "click":
            x, y = action.x, action.y
            button = (action.button or "left").lower()
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
            else:
                pyautogui.click(button=button)
        elif kind == "type" or kind == "input_text":
            if action.text:
                pyautogui.write(action.text, interval=0.02)
        elif kind == "type_text_at":
            if action.x is not None and action.y is not None:
                pyautogui.click(action.x, action.y)
                time.sleep(0.15)
            if action.extra.get("clear_before_typing", True):
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.05)
                pyautogui.press("backspace")
            if action.text:
                pyautogui.write(action.text, interval=0.02)
            if action.extra.get("press_enter", True):
                pyautogui.press("enter")
        elif kind == "scroll":
            dx = action.delta_x or 0
            dy = action.delta_y or 0
            if dx or dy:
                pyautogui.scroll(dy if dy else dx)
        elif kind == "scroll_at":
            # Scroll at (x,y): move to position then scroll (magnitude 0-999 → scroll clicks)
            x, y = action.x, action.y
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
            dy = action.delta_y or 0
            if dy:
                # Scale magnitude-ish to scroll steps (e.g. 800 → ~8)
                clicks = max(1, min(20, abs(dy) // 50)) * (1 if dy > 0 else -1)
                pyautogui.scroll(clicks)
        elif kind == "hover_at":
            x, y = action.x, action.y
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
        elif kind == "go_back":
            pyautogui.hotkey("alt", "left")
        elif kind == "go_forward":
            pyautogui.hotkey("alt", "right")
        elif kind == "search":
            import webbrowser
            try:
                webbrowser.open("https://www.google.com")
            except Exception as e:
                logger.warning("Could not open search: {}", e)
        elif kind == "navigate":
            url = (action.extra or {}).get("url", "")
            if url:
                import webbrowser
                try:
                    webbrowser.open(url)
                except Exception as e:
                    logger.warning("Could not navigate: {}", e)
        elif kind == "drag_and_drop":
            x, y = action.x, action.y
            dx = (action.extra or {}).get("destination_x")
            dy = (action.extra or {}).get("destination_y")
            if x is not None and y is not None and dx is not None and dy is not None:
                pyautogui.moveTo(x, y)
                time.sleep(0.05)
                pyautogui.drag(dx - x, dy - y, button="left")
        elif kind == "key" or kind == "keyboard":
            if action.key:
                key = action.key.strip()
                if "+" in key:
                    _map = {"control": "ctrl", "ctrl": "ctrl", "meta": "win", "command": "win"}
                    parts = [
                        _map.get(p.strip().lower(), p.strip().lower())
                        for p in key.split("+")
                        if p.strip()
                    ]
                    if len(parts) > 1:
                        pyautogui.hotkey(*parts)
                    else:
                        pyautogui.press(key)
                else:
                    pyautogui.press(key)
        elif kind == "wait":
            ms = action.duration_ms or 500
            time.sleep(ms / 1000.0)
        elif kind == "open_web_browser":
            import webbrowser
            try:
                webbrowser.open("about:blank")
            except Exception as e:
                logger.warning("Could not open browser: {}", e)
        else:
            logger.debug(
                "Computer use: unsupported tool event: kind={} (action skipped)",
                kind,
            )
            return kind
        return None

    async def execute(
        self,
        action: Action,
        *,
        requires_confirmation: bool = False,
    ) -> tuple[bool, str | None]:
        """
        Execute a single action. Returns (executed, unsupported_kind).
        executed: True if action ran, False if skipped (denied, dry_run, or unsupported).
        unsupported_kind: if action was not implemented, the kind name so the caller can exclude it next time.
        """
        if self.dry_run:
            self._logged.append(format_action(action, style="log"))
            return False, None

        if requires_confirmation and self.confirm_callback:
            ok = await self.confirm_callback(action)
            if not ok:
                return False, None

        err = _check_pyautogui()
        if err:
            logger.warning("Executor: {}", err)
            return False, None

        try:
            unsupported = self._execute_one(action)
            return unsupported is None, unsupported
        except Exception as e:
            logger.exception("Executor failed for {}: {}", action.kind, e)
            return False, None

    def get_dry_run_summary(self) -> str:
        """Return a summary of actions that would have been executed (when dry_run was True)."""
        if not self._logged:
            return "Dry run: no actions."
        return "Dry run: would have performed " + str(len(self._logged)) + " actions: " + "; ".join(self._logged[:20]) + ("; ..." if len(self._logged) > 20 else "")

    def clear_log(self) -> None:
        """Clear the dry-run log buffer."""
        self._logged.clear()
