---
name: nanobot-repo-context
description: Orients the agent in the nanobot repo using CLAUDE.md and docs. Use when starting a task, after a merge, or when adding a feature so conventions and extension points are followed.
---

# Nanobot repo context

When starting a task, after a merge, or when adding a feature in this repository:

1. **Read [CLAUDE.md](../../../CLAUDE.md)** at repo root for identity, self-improvement loop, and repo layout.
2. **Check docs as needed**:
   - Quick overview: [docs/output/](../../../docs/output/) (architecture, extension points, Playwright MCP).
   - Full reference: [docs/reference/](../../../docs/reference/) (file paths, classes, conventions, MCP schema).
3. **Apply conventions**: Prefer config and workspace over editing `nanobot/`. Put new behavior in `server/`, `frontend/`, or workspace bootstrap/skills.
4. When adding behavior, consider whether **docs or rules** should be updated; suggest edits if so (e.g. in docs/reference or docs/output).
5. For **new REST endpoints or services**, use the **add-backend-endpoint** skill. For **new API client or UI**, use the **add-frontend-api-and-ui** skill.
