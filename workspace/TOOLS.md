# Available Tools

This document describes the tools available to nanobot.

## File Operations

### read_file
Read the contents of a file.
```
read_file(path: str) -> str
```

### write_file
Write content to a file (creates parent directories if needed).
```
write_file(path: str, content: str) -> str
```

### edit_file
Edit a file by replacing specific text.
```
edit_file(path: str, old_text: str, new_text: str) -> str
```

### list_dir
List contents of a directory.
```
list_dir(path: str) -> str
```

## Shell Execution

### exec
Execute a shell command and return output.
```
exec(command: str, working_dir: str = None) -> str
```

**Safety Notes:**
- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- Optional `restrictToWorkspace` config to limit paths

## Web Access

### web_search
Search the web using Brave Search API.
```
web_search(query: str, count: int = 5) -> str
```

Returns search results with titles, URLs, and snippets. Requires `tools.web.search.apiKey` in config.

### web_fetch
Fetch and extract main content from a URL.
```
web_fetch(url: str, extractMode: str = "markdown", maxChars: int = 50000) -> str
```

**Notes:**
- Content is extracted using readability
- Supports markdown or plain text extraction
- Output is truncated at 50,000 characters by default

## Desktop control

### computer_use (prefer when available)

When the **computer_use** tool is available (enabled in config with a Gemini API key), **use it first** for multi-step desktop tasks such as "open Notepad and type X" or "click the Start button and open Settings". Call it once with a natural-language task; it captures the screen, asks a vision model for actions, and executes them until done. Do not compose screenshot → mouse_click → keyboard_type yourself for those tasks unless computer_use is unavailable or the user asks for low-level control.

```
computer_use(task: str) -> str
```
Example: `computer_use(task="open Notepad and type Hello from nanobot")`

### Low-level desktop tools

**When interacting with desktop UI** (taskbar, window previews, profile picker, icons), **always use screenshot_region then click_image**; do not rely on mouse_click with coordinates from the overlay. After a taskbar or icon click, call **get_foreground_window** to verify the intended window received focus; if it did not change, retry with click_image or use **launch_app** (e.g. Brave) as fallback. For browser profile pickers (e.g. Brave), prefer browser MCP with remote debugging when possible; if using CUA, focus the window first and use image-based click or keyboard (Tab + Enter) as fallback.

These tools control the machine nanobot runs on (mouse, keyboard, screenshot). They require approval by default (tool policy **ask**). Use them for direct control of the user's computer.

**CUA workflow:** (1) Prefer **browser/UI tools** (Playwright, cursor-ide-browser) for in-browser targets. (2) For **taskbar, window previews, icons**: use **screenshot_region** to capture the target area, then **click_image** with that base64; avoid **mouse_click** from overlay coordinates for these. (3) For other desktop clicks: take **screenshot** with `overlay_grid=True`, read (x,y) from the image, then **mouse_click(x,y)**. (4) Use **mouse_position** to calibrate if needed. (5) Use **run_python** for pyautogui **inline only** (no creating Python files); **pause and reflect** on screenshot results between steps.

### mouse_move
Move the mouse cursor to screen coordinates (x, y).
```
mouse_move(x: int, y: int) -> str
```

### mouse_click
Click at the given coordinates or at the current position. Button: left, right, or middle.
```
mouse_click(x: int = None, y: int = None, button: str = "left") -> str
```

### mouse_position
Return the current mouse cursor screen coordinates (x, y). Use to calibrate or verify position before clicking.
```
mouse_position() -> str
```

### keyboard_type
Type the given text using the keyboard (short strings; avoid special keys).
```
keyboard_type(text: str) -> str
```

### screenshot
Capture the full screen or a region (x, y, width, height). Returns base64 PNG. Use `overlay_grid=True` when you need to read coordinates for mouse_click (draws a coordinate grid on the image).
```
screenshot(x: int = None, y: int = None, width: int = None, height: int = None, overlay_grid: bool = False) -> str
```

### screenshot_region
Capture a region of the screen (x, y, width, height) and return the image as base64 PNG. Pass the return value to **locate_on_screen** or **click_image** to find and click that region on screen.
```
screenshot_region(x: int, y: int, width: int, height: int) -> str
```

### locate_on_screen
Find an image on the screen (provide image as base64 PNG). Returns bounding box and center (x, y). Optional region (left, top, width, height) limits the search; optional confidence (0–1) requires opencv-python.
```
locate_on_screen(image_base64: str, left: int = None, top: int = None, width: int = None, height: int = None, confidence: float = None) -> str
```

### click_image
Find an image on the screen (base64 PNG) and click at its center. Optional offset_x/offset_y; optional region and confidence.
```
click_image(image_base64: str, offset_x: int = 0, offset_y: int = 0, button: str = "left", ...) -> str
```

### get_foreground_window
Return the title of the current foreground (active) window. Use after clicking the taskbar or an icon to verify the intended window received focus. Windows only.
```
get_foreground_window() -> str
```

### launch_app
Launch an allowlisted application by name on Windows (e.g. brave, chrome, code). Use when UI clicks on the taskbar or desktop icons have failed. Windows only.
```
launch_app(app_name: str) -> str
```

## Communication

### message
Send a message to the user (used internally).
```
message(content: str, channel: str = None, chat_id: str = None) -> str
```

## Background Tasks

### spawn
Spawn a subagent to handle a task in the background.
```
spawn(task: str, label: str = None) -> str
```

Use for complex or time-consuming tasks that can run independently. The subagent will complete the task and report back when done.

## Scheduled Reminders (Cron)

Use the `exec` tool to create scheduled reminders with `nanobot cron add`:

### Set a recurring reminder
```bash
# Every day at 9am
nanobot cron add --name "morning" --message "Good morning! ☀️" --cron "0 9 * * *"

# Every 2 hours
nanobot cron add --name "water" --message "Drink water! 💧" --every 7200
```

### Set a one-time reminder
```bash
# At a specific time (ISO format)
nanobot cron add --name "meeting" --message "Meeting starts now!" --at "2025-01-31T15:00:00"
```

### Manage reminders
```bash
nanobot cron list              # List all jobs
nanobot cron remove <job_id>   # Remove a job
```

## Heartbeat Task Management

The `HEARTBEAT.md` file in the workspace is checked every 30 minutes.
Use file operations to manage periodic tasks:

### Add a heartbeat task
```python
# Append a new task
edit_file(
    path="HEARTBEAT.md",
    old_text="## Example Tasks",
    new_text="- [ ] New periodic task here\n\n## Example Tasks"
)
```

### Remove a heartbeat task
```python
# Remove a specific task
edit_file(
    path="HEARTBEAT.md",
    old_text="- [ ] Task to remove\n",
    new_text=""
)
```

### Rewrite all tasks
```python
# Replace the entire file
write_file(
    path="HEARTBEAT.md",
    content="# Heartbeat Tasks\n\n- [ ] Task 1\n- [ ] Task 2\n"
)
```

---

## Adding Custom Tools

To add custom tools:
1. Create a class that extends `Tool` in `nanobot/agent/tools/`
2. Implement `name`, `description`, `parameters`, and `execute`
3. Register it in `AgentLoop._register_default_tools()`
