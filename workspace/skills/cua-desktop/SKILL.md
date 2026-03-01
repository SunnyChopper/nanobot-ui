---
name: cua-desktop
description: Desktop automation (CUA) with pyautogui: when to use screenshot overlay, mouse_position, and run_python inline. Use when controlling the user's desktop (mouse, keyboard, screenshot).
always: true
---

# CUA desktop automation

Use this skill when you are controlling the user's desktop (mouse, keyboard, screenshot) so you get accurate coordinates and avoid mistakes.

## Workflow

1. **Prefer browser/UI tools** — For in-browser targets (e.g. clicking a button on a webpage), use Playwright MCP or cursor-ide-browser instead of pyautogui. If the goal is to **interact with an already-open browser or a specific browser profile** (e.g. Brave, "Nanobot" profile), use browser MCP with remote debugging instead of desktop clicking to focus the window. You are much less likely to make mistakes with UI tools than with coordinate-based scripts.

2. **Desktop clicks** — When you must use desktop tools:
   - **Taskbar, window previews, icons, or any small/fiddly UI element:** Do **not** use "read (x, y) from overlay then mouse_click". Instead: take a **screenshot** (full or region) to locate the target, then **screenshot_region(x, y, width, height)** to get a reference image of the target area, then **click_image(image_base64)** so PyAutoGUI finds and clicks it. This is much more reliable than coordinate guessing.
   - **After clicking taskbar or an icon:** Call **get_foreground_window** to confirm the intended window is focused. If the foreground window did not change, retry with **click_image** or use **launch_app** for known apps (e.g. Brave, Chrome; Windows only).
   - **Large, stable targets only:** You may use a **screenshot** with **overlay_grid=True**, read (x, y) from the overlay, then **mouse_click(x, y)** when image-based tools are not needed.
   - **Chromium/Electron windows (e.g. Brave profile picker):** Ensure the window is focused before clicking; if clicks still fail, use keyboard (Tab + Enter) via run_python.

3. **Calibrate with mouse_position** — Use **mouse_position** to get the current cursor (x, y) when you need to verify or calibrate (e.g. after moving the mouse).

4. **locate_on_screen / click_image** — When the target has a stable visual (e.g. icon), use **locate_on_screen** (image as base64 PNG) to get coordinates or **click_image** to find and click at center. Optional `region` and `confidence` (confidence requires opencv-python) improve accuracy.

5. **run_python for pyautogui** — Run pyautogui code **inline** via **run_python** only; do not create Python files. After each step (e.g. screenshot or click), **pause and reflect** on the result instead of barreling through.

## Summary

Use the screenshot overlay to read coordinates; use locate_on_screen/click_image when the target has a clear image; prefer UI tools for browser tasks; run pyautogui inline while reflecting on each step. If coordinates seem correct but clicks do not register, prefer image-based clicking and ensure the target window has focus (display scaling can affect the coordinate system).
