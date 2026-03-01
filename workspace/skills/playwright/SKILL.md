---
name: playwright
description: When to use headless vs remote debugging for browser automation (Playwright or cursor-ide-browser). Use when doing documentation research, scraping, or logging into sites like X.
---

# Playwright / browser automation

Use this skill when you use browser tools (e.g. `mcp_playwright_*` or Cursor’s browser MCP) so you choose the right mode.

## Headless vs remote debugging

- **Headless** — Use for:
  - Documentation research and reading public docs
  - Simple page fetches and content extraction
  - Scraping or automation that does not need a real login or session
  - Any task where the site does not rely on cookies, login, or complex JS auth

- **Remote debugging** — Use for:
  - Logging into an account (e.g. X/Twitter, GitHub, email)
  - Sites that require cookies or an existing session
  - Flows that need 2FA, OAuth, or “stay signed in”
  - When headless fails due to login walls or session checks

## When to use browser tools instead of desktop automation

When the task is to **check or control an already-open browser window** (e.g. Brave, Chrome) or a **specific profile** (e.g. "Nanobot" profile), **connect via remote debugging** and use browser tools (tabs, navigate, snapshot). Do **not** use desktop tools to click the taskbar or window preview to "focus" the browser; that is brittle. Prefer: ensure the browser is launched with remote debugging, then use MCP browser tools to interact with it.

## Summary

Use **headless** by default for docs and simple fetches. Switch to **remote debugging** when the task involves logging in or using an existing session (e.g. X engagement, posting, or reading a logged-in feed). For already-open browsers or specific profiles, use remote debugging and browser tools instead of CUA taskbar clicking.
