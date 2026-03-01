"""
OS-level desktop automation tools (mouse, keyboard, screenshot).

Uses PyAutoGUI; on Windows, pywinauto can be added for GUI control.
Gate with tool policy (e.g. "ask" or "deny") and optionally RBAC.
"""

import base64
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from nanobot.agent.tools.base import Tool
from nanobot.utils.helpers import ensure_windows_dpi_aware

# Prefix for screenshot tool result so the server can detect and inject image for the model.
SCREENSHOT_RESULT_PREFIX = "SCREENSHOT_BASE64:"


def _check_pyautogui() -> str | None:
    try:
        ensure_windows_dpi_aware()
        import pyautogui  # noqa: F401
        return None
    except ImportError:
        return "Desktop automation not available: install pyautogui (pip install pyautogui)"


def _draw_coordinate_overlay(im: Image.Image, step: int = 100) -> None:
    """Draw a coordinate grid and axis labels on the image (mutates in place)."""
    draw = ImageDraw.Draw(im)
    w, h = im.size
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    # Semi-transparent overlay would need Image.new("RGBA") and composite; use solid light lines
    color = (200, 200, 200)
    text_color = (80, 80, 80)
    # Vertical lines
    for x in range(0, w + 1, step):
        draw.line([(x, 0), (x, h)], fill=color, width=1)
        if font and x % (step * 2) == 0 and x > 0:
            draw.text((x - 10, 4), str(x), fill=text_color, font=font)
    # Horizontal lines
    for y in range(0, h + 1, step):
        draw.line([(0, y), (w, y)], fill=color, width=1)
        if font and y % (step * 2) == 0 and y > 0:
            draw.text((4, y - 8), str(y), fill=text_color, font=font)
    # Origin
    if font:
        draw.text((4, 4), "(0,0)", fill=text_color, font=font)


class MouseMoveTool(Tool):
    """Move the mouse to (x, y) on the screen."""

    @property
    def name(self) -> str:
        return "mouse_move"

    @property
    def description(self) -> str:
        return "Move the mouse cursor to the given screen coordinates (x, y)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate (pixels)"},
                "y": {"type": "integer", "description": "Y coordinate (pixels)"},
            },
            "required": ["x", "y"],
        }

    async def execute(self, x: int, y: int, **kwargs: Any) -> str:
        err = _check_pyautogui()
        if err:
            return err
        import pyautogui
        try:
            pyautogui.moveTo(x, y)
            return f"Moved mouse to ({x}, {y})"
        except Exception as e:
            return f"Error: {e}"


class MouseClickTool(Tool):
    """Click at (x, y) or at current position."""

    @property
    def name(self) -> str:
        return "mouse_click"

    @property
    def description(self) -> str:
        return "Click the mouse at the given coordinates or at current position. Button: left, right, or middle."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate (optional; current if omitted)"},
                "y": {"type": "integer", "description": "Y coordinate (optional)"},
                "button": {"type": "string", "description": "left, right, or middle", "default": "left"},
            },
            "required": [],
        }

    async def execute(self, x: int | None = None, y: int | None = None, button: str = "left", **kwargs: Any) -> str:
        err = _check_pyautogui()
        if err:
            return err
        import pyautogui
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
                return f"Clicked {button} at ({x}, {y})"
            pyautogui.click(button=button)
            return f"Clicked {button} at current position"
        except Exception as e:
            return f"Error: {e}"


class MousePositionTool(Tool):
    """Return the current mouse cursor position (x, y)."""

    @property
    def name(self) -> str:
        return "mouse_position"

    @property
    def description(self) -> str:
        return "Return the current mouse cursor screen coordinates (x, y). Use to calibrate or verify position before clicking."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: Any) -> str:
        err = _check_pyautogui()
        if err:
            return err
        import pyautogui
        try:
            x, y = pyautogui.position()
            return f"Current mouse position: ({x}, {y})"
        except Exception as e:
            return f"Error: {e}"


class KeyboardTypeTool(Tool):
    """Type a string using the keyboard."""

    @property
    def name(self) -> str:
        return "keyboard_type"

    @property
    def description(self) -> str:
        return "Type the given text using the keyboard. Use for short strings; avoid special keys."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to type"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str, **kwargs: Any) -> str:
        err = _check_pyautogui()
        if err:
            return err
        import pyautogui
        try:
            pyautogui.write(text, interval=0.02)
            return f"Typed {len(text)} characters"
        except Exception as e:
            return f"Error: {e}"


class ScreenshotTool(Tool):
    """Capture a screenshot (full screen or region) and return as base64 or save path."""

    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def description(self) -> str:
        return (
            "Capture a screenshot of the screen or a region (x, y, width, height). "
            "Returns base64 PNG. For small or moving targets (taskbar, icons, tabs), prefer screenshot_region then click_image; "
            "use overlay_grid=True and mouse_click(x,y) only for large, stable targets."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Left edge of region (omit for full screen)"},
                "y": {"type": "integer", "description": "Top edge of region"},
                "width": {"type": "integer", "description": "Width of region"},
                "height": {"type": "integer", "description": "Height of region"},
                "overlay_grid": {
                    "type": "boolean",
                    "description": "If true, draw a coordinate grid and axis labels on the image so you can read (x,y) for clicking.",
                    "default": False,
                },
            },
            "required": [],
        }

    async def execute(
        self,
        x: int | None = None,
        y: int | None = None,
        width: int | None = None,
        height: int | None = None,
        overlay_grid: bool = False,
        **kwargs: Any,
    ) -> str:
        err = _check_pyautogui()
        if err:
            return err
        import pyautogui
        try:
            if x is not None and y is not None and width is not None and height is not None:
                im = pyautogui.screenshot(region=(x, y, width, height))
            else:
                im = pyautogui.screenshot()
            if overlay_grid:
                # Ensure we have a format ImageDraw can use (e.g. RGB)
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGB")
                _draw_coordinate_overlay(im)
            buf = BytesIO()
            im.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            # Return with prefix so the server can inject this image into the next model turn.
            return SCREENSHOT_RESULT_PREFIX + b64
        except Exception as e:
            return f"Error: {e}"


class ScreenshotRegionTool(Tool):
    """Capture a region of the screen and return its base64 PNG for use with locate_on_screen or click_image."""

    @property
    def name(self) -> str:
        return "screenshot_region"

    @property
    def description(self) -> str:
        return (
            "Capture a region of the screen (x, y, width, height) and return the image as base64 PNG. "
            "Pass the return value to locate_on_screen or click_image to find and click that region on screen."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Left edge of region (pixels)"},
                "y": {"type": "integer", "description": "Top edge of region (pixels)"},
                "width": {"type": "integer", "description": "Width of region (pixels)"},
                "height": {"type": "integer", "description": "Height of region (pixels)"},
            },
            "required": ["x", "y", "width", "height"],
        }

    async def execute(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        **kwargs: Any,
    ) -> str:
        err = _check_pyautogui()
        if err:
            return err
        import pyautogui
        try:
            im = pyautogui.screenshot(region=(x, y, width, height))
            buf = BytesIO()
            im.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as e:
            return f"Error: {e}"


def _locate_image_on_screen(
    image_base64: str,
    region: tuple[int, int, int, int] | None = None,
    confidence: float | None = None,
) -> tuple[str, int | None, int | None]:
    """
    Locate an image on screen. Returns (message, center_x, center_y).
    center_x/y are None if not found.
    """
    import pyautogui

    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception as e:
        return f"Invalid base64 image: {e}", None, None
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as f:
        f.write(raw)
        f.flush()
        path = Path(f.name)
        kwargs: dict[str, Any] = {}
        if region is not None:
            kwargs["region"] = region
        if confidence is not None:
            kwargs["confidence"] = confidence
        try:
            box = pyautogui.locateOnScreen(str(path), **kwargs)
        except Exception as e:
            return f"Image not found on screen: {e}", None, None
    if box is None:
        return "Image not found on screen.", None, None
    center = pyautogui.center(box)
    msg = (
        f"Found at left={box.left}, top={box.top}, width={box.width}, height={box.height}; "
        f"center=({center.x}, {center.y})"
    )
    return msg, center.x, center.y


class LocateOnScreenTool(Tool):
    """Find an image on screen and return its bounding box and center coordinates."""

    @property
    def name(self) -> str:
        return "locate_on_screen"

    @property
    def description(self) -> str:
        return (
            "Find an image on the screen (provide image as base64 PNG). "
            "Returns bounding box (left, top, width, height) and center (x, y). "
            "Use optional region to limit search; optional confidence (0-1) requires opencv-python."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded PNG image to find on screen"},
                "left": {"type": "integer", "description": "Left edge of search region (optional)"},
                "top": {"type": "integer", "description": "Top edge of search region (optional)"},
                "width": {"type": "integer", "description": "Width of search region (optional)"},
                "height": {"type": "integer", "description": "Height of search region (optional)"},
                "confidence": {"type": "number", "description": "Match confidence 0-1 (optional; requires opencv-python)"},
            },
            "required": ["image_base64"],
        }

    async def execute(
        self,
        image_base64: str,
        left: int | None = None,
        top: int | None = None,
        width: int | None = None,
        height: int | None = None,
        confidence: float | None = None,
        **kwargs: Any,
    ) -> str:
        err = _check_pyautogui()
        if err:
            return err
        region = None
        if left is not None and top is not None and width is not None and height is not None:
            region = (left, top, width, height)
        msg, _, _ = _locate_image_on_screen(image_base64, region=region, confidence=confidence)
        return msg


class ClickImageTool(Tool):
    """Find an image on screen and click at its center (optional offset)."""

    @property
    def name(self) -> str:
        return "click_image"

    @property
    def description(self) -> str:
        return (
            "Find an image on the screen (base64 PNG), then click at its center. "
            "Optional offset_x/offset_y adjust the click from center. Optional region and confidence."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded PNG image to find and click"},
                "offset_x": {"type": "integer", "description": "Pixels to add to center X (optional)", "default": 0},
                "offset_y": {"type": "integer", "description": "Pixels to add to center Y (optional)", "default": 0},
                "button": {"type": "string", "description": "left, right, or middle", "default": "left"},
                "left": {"type": "integer", "description": "Left edge of search region (optional)"},
                "top": {"type": "integer", "description": "Top edge of search region (optional)"},
                "width": {"type": "integer", "description": "Width of search region (optional)"},
                "height": {"type": "integer", "description": "Height of search region (optional)"},
                "confidence": {"type": "number", "description": "Match confidence 0-1 (optional; requires opencv-python)"},
            },
            "required": ["image_base64"],
        }

    async def execute(
        self,
        image_base64: str,
        offset_x: int = 0,
        offset_y: int = 0,
        button: str = "left",
        left: int | None = None,
        top: int | None = None,
        width: int | None = None,
        height: int | None = None,
        confidence: float | None = None,
        **kwargs: Any,
    ) -> str:
        err = _check_pyautogui()
        if err:
            return err
        region = None
        if left is not None and top is not None and width is not None and height is not None:
            region = (left, top, width, height)
        msg, cx, cy = _locate_image_on_screen(image_base64, region=region, confidence=confidence)
        if cx is None or cy is None:
            return msg
        import pyautogui
        try:
            pyautogui.click(cx + offset_x, cy + offset_y, button=button)
            return f"Clicked {button} at ({cx + offset_x}, {cy + offset_y}). {msg}"
        except Exception as e:
            return f"Error clicking: {e}"


def _get_foreground_window_title_win() -> str | None:
    """Return the title of the foreground window on Windows, or None if unsupported/failed."""
    if sys.platform != "win32":
        return None
    try:
        ctypes = __import__("ctypes")
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return None


class GetForegroundWindowTool(Tool):
    """Return the title of the current foreground window (Windows). Use after a click to verify focus changed."""

    @property
    def name(self) -> str:
        return "get_foreground_window"

    @property
    def description(self) -> str:
        return (
            "Return the title of the current foreground (active) window. "
            "Use after clicking the taskbar or an icon to verify the intended window received focus. "
            "Only supported on Windows."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        if sys.platform != "win32":
            return "get_foreground_window is only supported on Windows."
        title = _get_foreground_window_title_win()
        if title is None:
            return "Could not get foreground window title."
        return f"foreground_window: {title!r}"


# Built-in allowlist for launch_app (app_name -> exe path). Config can extend via LaunchAppTool(allowlist=...).
import os as _os
DEFAULT_LAUNCH_APP_ALLOWLIST: dict[str, str] = {
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "code": _os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
}


class LaunchAppTool(Tool):
    """Launch an allowlisted application by name on Windows. Use when taskbar/icon clicks fail."""

    def __init__(self, allowlist: dict[str, str] | None = None) -> None:
        self._allowlist = allowlist if allowlist is not None else DEFAULT_LAUNCH_APP_ALLOWLIST.copy()

    @property
    def name(self) -> str:
        return "launch_app"

    @property
    def description(self) -> str:
        return (
            "Launch an application by name on Windows (allowlist only). "
            "Use when UI clicks on the taskbar or desktop icons have failed. "
            "Pass app_name (e.g. brave, chrome, code). Only supported on Windows."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name (e.g. brave, chrome, code)"},
            },
            "required": ["app_name"],
        }

    async def execute(self, app_name: str, **kwargs: Any) -> str:
        if sys.platform != "win32":
            return "launch_app is only supported on Windows."
        key = app_name.strip().lower()
        path = self._allowlist.get(key)
        if not path or not Path(path).exists():
            allowed = ", ".join(sorted(self._allowlist.keys()))
            return f"App {app_name!r} not in allowlist or path not found. Allowed: {allowed}"
        try:
            ctypes = __import__("ctypes")
            ctypes.windll.shell32.ShellExecuteW(None, "open", path, None, None, 1)
            return f"Launched {app_name!r} ({path})"
        except Exception as e:
            return f"Error launching {app_name!r}: {e}"
