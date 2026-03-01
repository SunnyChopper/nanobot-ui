"""Gemini 2.5 Computer Use provider (computer_use tool). Uses REST API for reliable key and request format."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from io import BytesIO
from typing import Any

from loguru import logger

from nanobot.agent.computer_use.base import Action, ActionResponse
from nanobot.agent.computer_use.capture import capture_screen_png
from nanobot.agent.computer_use.formatting import format_action

_GEMINI_REST_BASE = "https://generativelanguage.googleapis.com/v1beta"
_MODEL = "gemini-3-flash-preview"
# Downscale screenshots above this size to avoid 404 with image+computer_use (probe works without image).
_MAX_SCREENSHOT_BYTES = 250_000
_DEBUG_LOG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".cursor", "debug.log")
)


def _debug_log(message: str, data: dict[str, Any] | None = None, hypothesis_id: str | None = None) -> None:
    # #region agent log
    try:
        import time
        payload = {"timestamp": int(time.time() * 1000), "location": "gemini_provider", "message": message}
        if data:
            payload["data"] = data
        if hypothesis_id:
            payload["hypothesisId"] = hypothesis_id
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
    # #endregion
_MAX_DIMENSION = 1280
_MAX_DIMENSION_FIRST_STEP = 1600  # step 1 only: more detail for initial plan and first click
_JPEG_QUALITY = 82


def _get_image_size(png_bytes: bytes) -> tuple[int, int] | None:
    """Return (width, height) of the image from PNG/JPEG bytes. Uses same coordinate system as capture."""
    if not png_bytes or len(png_bytes) < 24:
        return None
    try:
        from PIL import Image
        img = Image.open(BytesIO(png_bytes))
        return img.size
    except Exception:
        return None


def _downscale_screenshot_if_needed(
    png_bytes: bytes,
    step_index: int | None = None,
) -> tuple[bytes, str]:
    """If png_bytes exceeds _MAX_SCREENSHOT_BYTES, resize and re-encode as JPEG. Returns (bytes, mime_type). step_index=1 uses a larger max dimension."""
    if len(png_bytes) <= _MAX_SCREENSHOT_BYTES:
        return png_bytes, "image/png"
    max_dim = _MAX_DIMENSION_FIRST_STEP if step_index == 1 else _MAX_DIMENSION
    try:
        from PIL import Image

        img = Image.open(BytesIO(png_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            nw, nh = int(w * scale), int(h * scale)
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        out = buf.getvalue()
        return out, "image/jpeg"
    except Exception as e:
        logger.debug("Screenshot downscale skipped: {}", e)
        return png_bytes, "image/png"


def _denormalize_coord(val: int | float | None, size: int) -> int:
    """Convert Gemini normalized coordinate (0–999) to pixel (0–size-1)."""
    if val is None:
        return 0
    return max(0, min(size - 1, int(float(val) / 1000 * size)))


def _parse_action_from_call(
    name: str,
    args: dict[str, Any],
    screen_width: int | None = None,
    screen_height: int | None = None,
) -> Action | None:
    """Map a function_call name + args to an Action. Gemini uses 0–999 coords; denormalize if size given."""
    kind = name.lower().replace("-", "_").strip()
    sw = screen_width or 1920
    sh = screen_height or 1080

    if kind in ("click", "mouse_click", "pointer_click", "click_at"):
        x, y = args.get("x"), args.get("y")
        if x is not None and y is not None:
            x = _denormalize_coord(x, sw)
            y = _denormalize_coord(y, sh)
        return Action(
            kind="click",
            x=x,
            y=y,
            button=args.get("button") or args.get("mouse_button") or "left",
        )
    if kind in ("type", "input_text", "keyboard_type", "type_text"):
        text = args.get("text") or args.get("input") or ""
        if not text:
            return None
        return Action(kind="type", text=text)
    if kind == "type_text_at":
        text = args.get("text") or args.get("input") or ""
        if not text:
            return None
        x, y = args.get("x"), args.get("y")
        if x is not None and y is not None:
            x = _denormalize_coord(x, sw)
            y = _denormalize_coord(y, sh)
        return Action(
            kind="type_text_at",
            x=x,
            y=y,
            text=text,
            extra={
                "press_enter": args.get("press_enter", True),
                "clear_before_typing": args.get("clear_before_typing", True),
            },
        )
    if kind in ("scroll", "scroll_delta", "scroll_document"):
        direction = (args.get("direction") or "").lower()
        dy = 0
        if direction in ("down", "right"):
            dy = -300
        elif direction in ("up", "left"):
            dy = 300
        return Action(kind="scroll", delta_x=int(args.get("delta_x", 0) or 0), delta_y=dy)
    if kind == "scroll_at":
        x, y = args.get("x"), args.get("y")
        if x is not None and y is not None:
            x = _denormalize_coord(x, sw)
            y = _denormalize_coord(y, sh)
        direction = (args.get("direction") or "down").lower()
        magnitude = int(args.get("magnitude", 800) or 800)
        magnitude = max(0, min(999, magnitude))
        return Action(
            kind="scroll_at",
            x=x,
            y=y,
            delta_y=-magnitude if direction in ("down", "right") else magnitude,
            extra={"direction": direction},
        )
    if kind == "hover_at":
        x, y = args.get("x"), args.get("y")
        if x is not None and y is not None:
            x = _denormalize_coord(x, sw)
            y = _denormalize_coord(y, sh)
        return Action(kind="hover_at", x=x, y=y)
    if kind == "go_back":
        return Action(kind="go_back")
    if kind == "go_forward":
        return Action(kind="go_forward")
    if kind == "search":
        return Action(kind="search")
    if kind == "navigate":
        url = args.get("url") or ""
        if not url:
            return None
        return Action(kind="navigate", extra={"url": url})
    if kind == "drag_and_drop":
        x, y = args.get("x"), args.get("y")
        dest_x, dest_y = args.get("destination_x"), args.get("destination_y")
        if x is not None and y is not None and dest_x is not None and dest_y is not None:
            x = _denormalize_coord(x, sw)
            y = _denormalize_coord(y, sh)
            dest_x = _denormalize_coord(dest_x, sw)
            dest_y = _denormalize_coord(dest_y, sh)
        return Action(
            kind="drag_and_drop",
            x=x,
            y=y,
            extra={"destination_x": dest_x, "destination_y": dest_y},
        )
    if kind in ("key", "keyboard", "press_key", "key_down", "key_combination"):
        keys = args.get("keys") or args.get("key") or args.get("key_name")
        if keys:
            return Action(kind="key", key=keys)
    if kind == "wait" or kind == "wait_5_seconds":
        duration = 5000 if kind == "wait_5_seconds" else (args.get("duration_ms", 500) or args.get("duration", 500))
        return Action(kind="wait", duration_ms=int(duration))
    # Unrecognized: return as generic so executor can report unsupported
    return Action(kind=kind, extra=dict(args))


def _parse_response_to_actions(
    response: Any,
    screen_width: int | None = None,
    screen_height: int | None = None,
) -> tuple[list[Action], bool, bool]:
    """
    Parse Gemini generate_content response into (actions, done, requires_confirmation).
    Handles response.function_calls (SDK convenience), function_call in parts, and text indicating done.
    If screen_width/height are set, Gemini's 0–999 coordinates are denormalized to pixels.
    """
    actions: list[Action] = []
    done = False
    requires_confirmation = False

    def parse_one(name: str, args: dict[str, Any]) -> Action | None:
        return _parse_action_from_call(name, args, screen_width, screen_height)

    try:
        # REST JSON uses camelCase (candidates[].content.parts[].functionCall)
        if isinstance(response, dict):
            candidates = response.get("candidates", [])
            if candidates and isinstance(candidates[0], dict):
                c0 = candidates[0]
                content = c0.get("content") or {}
                parts = content.get("parts") or []
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    fn = part.get("functionCall") or part.get("function_call")
                    if fn:
                        name = (fn.get("name") or "").strip()
                        args = fn.get("args") or {}
                        if name and "done" in name.lower():
                            done = True
                            continue
                        act = parse_one(name, args)
                        if act:
                            actions.append(act)
                    else:
                        txt = part.get("text")
                        if txt and not actions:
                            done = True
                return actions, done, requires_confirmation
            return actions, done, requires_confirmation

        # SDK may expose function_calls as a list on the response
        fn_calls = getattr(response, "function_calls", None)
        if fn_calls:
            for fc in fn_calls:
                name = getattr(fc, "name", None) or (fc.get("name") if isinstance(fc, dict) else "")
                args = getattr(fc, "args", None)
                if args is None and isinstance(fc, dict):
                    args = fc.get("args", {})
                if isinstance(args, dict):
                    pass
                elif hasattr(args, "items"):
                    args = dict(args)
                else:
                    args = {}
                if name and "done" in str(name).lower():
                    done = True
                    continue
                act = parse_one(str(name), args or {})
                if act:
                    actions.append(act)
            return actions, done, requires_confirmation

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return actions, done, requires_confirmation

        content = getattr(candidates[0], "content", None)
        if not content:
            return actions, done, requires_confirmation

        parts = getattr(content, "parts", None) or []
        text_parts: list[str] = []

        for part in parts:
            # Function call (tool use)
            fn = getattr(part, "function_call", None)
            if fn:
                name = getattr(fn, "name", None) or ""
                args = getattr(fn, "args", None)
                if isinstance(args, dict):
                    pass
                elif hasattr(args, "items"):
                    args = dict(args)
                else:
                    args = {}
                if name and "done" in name.lower():
                    done = True
                    continue
                act = parse_one(name, args or {})
                if act:
                    actions.append(act)
                continue

            # Text
            txt = getattr(part, "text", None)
            if txt:
                text_parts.append(txt)

        # Check finish reason
        finish_reason = getattr(candidates[0], "finish_reason", None) or ""
        if str(finish_reason).endswith("STOP") or "stop" in str(finish_reason).lower():
            if not actions and text_parts:
                done = True

        # Safety / confirmation (e.g. safety_metadata or prompt_feedback)
        safety = getattr(response, "prompt_feedback", None) or getattr(
            response, "safety_metadata", None
        )
        if safety and getattr(safety, "block_reason", None):
            requires_confirmation = True
    except Exception as e:
        logger.warning("Parse Gemini computer use response: {}", e)

    return actions, done, requires_confirmation


class GeminiComputerUseProvider:
    """Computer use backend using Gemini 2.5 / SDK. Uses GEMINI_API_KEY."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-flash-preview",
        excluded_predefined_functions: list[str] | None = None,
        prefer_keyboard_shortcuts: bool = True,
        allow_multi_action_turn: bool = True,
        use_conversation_history: bool = False,
    ):
        self._api_key = api_key
        self._model = model
        self._excluded = excluded_predefined_functions or []
        self._prefer_keyboard_shortcuts = prefer_keyboard_shortcuts
        self._allow_multi_action_turn = allow_multi_action_turn
        self._use_conversation_history = use_conversation_history

    def _api_key_for_request(self) -> str:
        """Prefer GEMINI_API_KEY so computer use works (REST generativelanguage API); SDK prefers GOOGLE_API_KEY which can 404."""
        return (os.environ.get("GEMINI_API_KEY") or "").strip() or (self._api_key or "").strip()

    def capture_screen(self) -> bytes:
        """Return PNG bytes of the current screen."""
        return capture_screen_png()

    def probe_api_key(self) -> bool:
        """Send a minimal text-only request to verify the key and model. Returns True if 200, False if 404."""
        key = self._api_key_for_request()
        if not key:
            return False
        body = {
            "contents": [{"parts": [{"text": "Say ok"}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 10},
        }
        try:
            self._rest_generate_content(body)
            return True
        except RuntimeError as e:
            if "404" in str(e):
                return False
            raise

    def _rest_generate_content(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST to generativelanguage v1beta; body is GenerateContent request. Raises on HTTP error."""
        key = self._api_key_for_request()
        if not key:
            raise ValueError("No API key for Gemini computer use. Set GEMINI_API_KEY or configure tools.computerUse.apiKey.")
        # Send key in header (required by some clients) and query (matches working curl test)
        url = f"{_GEMINI_REST_BASE}/models/{self._model}:generateContent?key={key}"
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body_bytes = e.read()
            try:
                err_body = json.loads(body_bytes.decode())
            except Exception:
                err_body = {"error": {"message": body_bytes.decode()[:500]}}
            if e.code == 404:
                logger.warning(
                    "Gemini 404 response body (for debugging): {}",
                    json.dumps(err_body)[:1000],
                )
                req_shape = {}
                try:
                    body_copy = json.loads(data.decode()) if isinstance(data, bytes) else {}
                    req_shape = {
                        "body_keys": list(body_copy.keys()),
                        "has_tools": "tools" in body_copy,
                        "first_content_parts": [
                            list(p.keys())[0] if isinstance(p, dict) else "?"
                            for p in (body_copy.get("contents") or [{}])[0].get("parts") or []
                        ],
                    }
                except Exception:
                    pass
                _debug_log(
                    "404 response from Gemini",
                    data={"http_code": 404, "response_body": err_body, "request_shape": req_shape},
                    hypothesis_id="H2_H3_H5",
                )
                key_source = "GEMINI_API_KEY (env)" if os.environ.get("GEMINI_API_KEY") else "config"
                raise RuntimeError(
                    f"404 Not Found. The API key is set (from {key_source}) but the server returned 404. "
                    "This can mean: (1) the model is not available for your key/region, or (2) the request format. "
                    "From the same environment where you start the server, run: python scripts/test_gemini_computer_use.py "
                    "If that succeeds, the key works—then the 404 may be due to request size (large screenshot)."
                ) from e
            raise RuntimeError(f"{e.code} {e.reason}. {err_body}") from e

    async def send_action_request(
        self,
        screenshot_bytes: bytes,
        task: str,
        history: list[dict[str, Any]] | None = None,
        step_index: int | None = None,
        step_limit: int | None = None,
        excluded_actions_this_run: list[str] | None = None,
        hints: list[str] | None = None,
        actions_taken_this_run: list[dict[str, Any]] | None = None,
        screen_unchanged_since_last: bool = False,
        same_action_repeated_count: int = 0,
        last_repeated_action_summary: dict[str, Any] | None = None,
        same_kind_streak: int = 0,
        same_kind_name: str | None = None,
        oscillating: bool = False,
    ) -> ActionResponse:
        """Send screenshot + task to Gemini with computer_use tool; return ActionResponse."""
        import asyncio

        if not screenshot_bytes or len(screenshot_bytes) < 100:
            raise ValueError(
                "Screenshot is missing or too small to send. "
                "Capture must return non-empty PNG bytes before calling send_action_request."
            )

        def _run() -> ActionResponse:
            payload_bytes, mime_type = _downscale_screenshot_if_needed(
                screenshot_bytes, step_index=step_index
            )
            if mime_type != "image/png" and len(screenshot_bytes) > _MAX_SCREENSHOT_BYTES:
                logger.debug(
                    "Computer use: downscaled screenshot {} -> {} bytes ({})",
                    len(screenshot_bytes),
                    len(payload_bytes),
                    mime_type,
                )
            task_text = task or "What should I do next on this screen?"
            # Step budget: so the model knows how many steps remain
            if step_index is not None and step_limit is not None and step_limit > 0:
                task_text = (
                    f"Step {step_index} of {step_limit}. Do the next action or respond with done if the goal is achieved. "
                    + task_text
                )
            if screen_unchanged_since_last:
                task_text = "Screen unchanged after the previous action; try a different action. " + task_text
            # Stronger hint when the same action was repeated and/or screen did not change
            if same_action_repeated_count >= 2 and last_repeated_action_summary:
                formatted = format_action(last_repeated_action_summary, style="prompt", max_len=30)
                repetition_msg = (
                    "You have already performed the same action (e.g. "
                    + formatted
                    + ") multiple times; the screen may be unchanged. "
                    "Try a different action (scroll, different click, or keyboard) or respond with done. "
                )
                # For positional actions (click, etc.), add explicit "do not click at/near same position"
                if last_repeated_action_summary.get("x") is not None and last_repeated_action_summary.get("y") is not None:
                    repetition_msg = (
                        "Do not click again at or near the same position; try a different element or say done. "
                        + repetition_msg
                    )
                task_text = repetition_msg + task_text
            elif screen_unchanged_since_last and same_action_repeated_count == 1:
                task_text = (
                    "The screen did not change after your last action. "
                    "Do NOT repeat the same click/action; try a different action or say you are done. "
                    + task_text
                )
            # Same-kind streak: last N actions were all the same kind (e.g. scroll_at)
            if same_kind_streak >= 1 and same_kind_name:
                task_text = (
                    f"The last {same_kind_streak} actions were all {same_kind_name}. "
                    "If the goal is not advanced, try a different action (e.g. click, type, or keyboard) or respond with done. "
                    + task_text
                )
            # Oscillation: alternating between two actions
            if oscillating:
                task_text = (
                    "You are alternating between two actions; try something different or respond with done. "
                    + task_text
                )
            if hints:
                task_text = (
                    "Relevant past runs (use to avoid repeating mistakes and to reuse working strategies):\n"
                    + "\n".join(hints)
                    + "\n\nTask: "
                    + task_text
                )
            if actions_taken_this_run:
                parts = []
                for i, a in enumerate(actions_taken_this_run[-15:], start=1):
                    part = format_action(a, style="prompt", max_len=40)
                    parts.append(f"{i}. {part}")
                run_summary = " ".join(parts)
                task_text = (
                    "Actions already taken in this run (do NOT repeat): "
                    + run_summary
                    + ". Now do only the NEXT action needed. Goal: "
                    + task_text
                )
                # Recent action kinds summary: when >=4 of last 6 are same kind, show the list
                recent = actions_taken_this_run[-8:]
                if len(recent) >= 4:
                    kinds = [(a.get("kind") or "?").strip() for a in recent[-6:]]
                    from collections import Counter
                    cnt = Counter(kinds)
                    if cnt and max(cnt.values()) >= 4:
                        kinds_str = ", ".join(kinds)
                        task_text = (
                            f"Last {len(kinds)} actions: {kinds_str}. "
                            "If you are repeating the same type of action without progress, try something different or respond with done. "
                            + task_text
                        )
            # From step 2 onward: guide the model (one action vs short sequence) and avoid repeating what's already done.
            if step_index is not None and step_index > 1:
                if self._allow_multi_action_turn:
                    task_text = (
                        f"Step {step_index}. Look at the current screen. "
                        "Perform the next action or a short sequence of actions in one turn when the next steps are clear (e.g. click at target then type, or hover then click). "
                        "Do NOT repeat actions already done (e.g. if an application is already open, do not open it again—focus in it, type in it, or close dialogs; then continue). "
                        "Goal: " + task_text
                    )
                else:
                    task_text = (
                        f"Step {step_index}. Look at the current screen. "
                        "Perform only the NEXT action needed to achieve the goal. "
                        "Do NOT repeat actions already done (e.g. if an application is already open, do not open it again—focus in it, type in it, or close dialogs; then continue). "
                        "Goal: " + task_text
                    )
            if self._prefer_keyboard_shortcuts:
                task_text = (
                    "Prefer keyboard shortcuts and key presses whenever possible (e.g. Win+R, type, Enter; Ctrl+O to open). "
                    "Use mouse clicks only when necessary (e.g. when no shortcut exists or the target has no keyboard path). "
                    "Task: " + task_text
                )
            # Use key from _api_key_for_request() (GEMINI_API_KEY when set). The SDK may log "Using GOOGLE_API_KEY"
            # when both env vars are set; the request is sent with the key we pass here.
            key = self._api_key_for_request()
            excluded = list(self._excluded)
            if excluded_actions_this_run:
                for name in excluded_actions_this_run:
                    if name and name not in excluded:
                        excluded.append(name)

            # Prefer official SDK (matches https://ai.google.dev/gemini-api/docs/computer-use#send-request)
            sdk_contents_for_history: list[Any] = []
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=key)
                computer_use_kw: dict[str, Any] = {
                    "environment": types.Environment.ENVIRONMENT_BROWSER,
                }
                if excluded:
                    computer_use_kw["excluded_predefined_functions"] = excluded
                config = types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            computer_use=types.ComputerUse(**computer_use_kw)
                        )
                    ],
                    temperature=0.2,
                )
                # Doc order: text then image (Part(text=...), Part.from_bytes(...))
                current_user_content = types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=task_text),
                        types.Part.from_bytes(data=payload_bytes, mime_type=mime_type),
                    ],
                )
                if self._use_conversation_history and history:
                    # history is list of types.Content from previous contents_for_history; cap to last 3 exchanges
                    contents = list(history)[-6:] + [current_user_content]
                else:
                    contents = [current_user_content]
                response = client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                if self._use_conversation_history and response.candidates:
                    model_content = response.candidates[0].content
                    sdk_contents_for_history[:] = contents + [model_content]
                    sdk_contents_for_history[:] = sdk_contents_for_history[-6:]
            except Exception as sdk_err:
                # Fall back to REST (same request shape we used before)
                logger.debug("Computer use SDK request failed, falling back to REST: {}", sdk_err)
                b64 = base64.standard_b64encode(payload_bytes).decode("ascii")
                contents = [
                    {
                        "role": "user",
                        "parts": [
                            {"inlineData": {"mimeType": mime_type, "data": b64}},
                            {"text": task_text},
                        ],
                    }
                ]
                # REST expects dict contents; history from SDK is list of Content objects — only use when dicts
                if history and all(isinstance(h, dict) for h in history):
                    for h in history[-6:]:
                        role = h.get("role") or "user"
                        parts = h.get("parts") or h.get("content")
                        if isinstance(parts, str):
                            parts = [{"text": parts}]
                        if parts:
                            contents.append({"role": role, "parts": parts})
                tools_payload: dict[str, Any] = {"environment": "ENVIRONMENT_BROWSER"}
                if excluded:
                    tools_payload["excludedPredefinedFunctions"] = excluded
                body = {
                    "contents": contents,
                    "generationConfig": {"temperature": 0.2},
                    "tools": [{"computerUse": tools_payload}],
                }
                _debug_log(
                    "send_action_request body shape (REST fallback)",
                    data={"model": self._model, "body_keys": list(body.keys())},
                    hypothesis_id="H1_H4_H5",
                )
                response = self._rest_generate_content(body)

            # Use screenshot dimensions for coordinate mapping so clicks match the same coordinate system as capture (avoids DPI/scaling mismatch).
            size_from_image = _get_image_size(screenshot_bytes)
            if size_from_image:
                screen_w, screen_h = size_from_image
            else:
                try:
                    from nanobot.utils.helpers import ensure_windows_dpi_aware
                    ensure_windows_dpi_aware()
                    import pyautogui
                    screen_w, screen_h = pyautogui.size()
                except Exception:
                    screen_w, screen_h = 1920, 1080
            actions, done, requires_confirmation = _parse_response_to_actions(
                response, screen_width=screen_w, screen_height=screen_h
            )
            return ActionResponse(
                actions=actions,
                done=done,
                message=None,
                requires_confirmation=requires_confirmation,
                contents_for_history=sdk_contents_for_history,
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)
