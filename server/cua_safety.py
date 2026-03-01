"""CUA inline-Python safety check via a fast Groq model."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are a security classifier for inline Python code run by an AI assistant doing desktop automation.
Reply with exactly one line: either "SAFE" or "UNSAFE" followed by a short reason.

SAFE only if ALL of these hold:
- Code only uses: pyautogui, time, and standard library (math, etc.) for desktop automation (mouse, keyboard, screenshot).
- Typing URLs or opening browser tabs via pyautogui (keyboard input only) is SAFE; the code does not perform network I/O.
- No exec(), eval(), compile(), or similar that execute arbitrary strings.
- No network access from the code (requests, socket, urllib, etc.).
- No subprocess.run() or os.system() with user-controlled or arbitrary commands.
- No file writes outside temporary directories or reading sensitive paths (e.g. .env, .ssh, passwords).
- No privilege escalation or destructive system calls.

Otherwise reply UNSAFE."""


async def is_safe_python_for_cua(
    code: str,
    model: str,
    api_key: str | None,
    timeout_seconds: float = 8.0,
) -> bool:
    """
    Return True if the code is classified as safe for CUA auto-approve (pyautogui-only desktop automation).
    Uses Groq's fast model. On error or missing key, returns False (so we fall back to user approval).
    """
    if not api_key or not api_key.strip():
        return False
    code = (code or "").strip()
    if not code:
        return False
    model = (model or "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify this Python code:\n\n```python\n{code[:8000]}\n```"},
        ],
        "max_tokens": 80,
        "temperature": 0,
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                GROQ_CHAT_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=timeout_seconds,
            )
        r.raise_for_status()
        data = r.json()
        content = (
            (data.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            .upper()
        )
        safe = content.startswith("SAFE")
        if not safe:
            logger.info("CUA safety check: UNSAFE or unclear - %s", content[:200])
        return safe
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.warning(
                "CUA safety check: Groq returned 403 Forbidden. Check your Groq API key at Settings → Providers → Groq, "
                "and ensure the key is valid and has access to chat completions (see console.groq.com)."
            )
        else:
            logger.warning("CUA safety check failed (HTTP %s): %s", e.response.status_code, e)
        return False
    except Exception as e:
        logger.warning("CUA safety check failed: %s", e)
        return False
