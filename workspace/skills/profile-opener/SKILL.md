---
name: profile-opener
description: Opening or switching to a specific browser profile (e.g. Brave "Nanobot") when the profile picker or taskbar is involved. Use when the user asks to open a browser profile or select one from the Brave/Chrome profile picker.
---

# Profile Opener

Use this skill when opening or switching to a specific browser profile (e.g. Brave "Nanobot") and the profile picker or taskbar is involved.

## Preferred method

Use **browser MCP** (Playwright / cursor-ide-browser) with **remote debugging** so you connect to the already-running browser and use tabs/navigate. Avoid desktop clicking when possible.

## If using desktop (CUA)

1. **Image-based click:** Use **screenshot_region** to capture the profile card (or the Brave window), then **click_image** to click it. Do **not** rely on coordinate-based mouse_click for the profile card.

2. **Focus first:** If the click does not seem to work, ensure the Brave window has focus. Use **screenshot_region** on the window (e.g. title bar or any visible part), then **click_image** on that image so the window is focused. Then try **click_image** again on the profile card image.

3. **Detect failure:** After a click, take a **screenshot** (or screenshot_region of the picker area). If the profile picker is still visible, the selection likely failed.

4. **Retry with keyboard:** Ensure the Brave window has focus (step 2). Then use **run_python** to run:
   - `import pyautogui; pyautogui.press('tab')` (possibly multiple times, e.g. 1–4 times depending on which profile is first)
   - then `pyautogui.press('enter')`
   If the first profile is the target, a single Enter might suffice; otherwise Tab to the correct card then Enter.

## Screen scaling

If coordinates seem correct but clicks do not register, consider display scaling (e.g. 100% vs 125%). Prefer image-based clicking (screenshot_region + click_image) over coordinate-based mouse_click.
