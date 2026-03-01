# Cognitive framework for coding agents

You are a coding agent working in the **nanobot** repository. Follow this file and the linked docs for consistency and self-improvement.

## Identity and role

- Work in this repo according to the conventions and extension points documented here and in [docs/](docs/).
- Prefer **extending** via config, workspace files, [server/](server/), and [frontend/](frontend/) rather than editing the core engine.
- When in doubt, read the relevant doc before making large changes.

## Self-improvement loop

1. **Before large changes**: Read [docs/README.md](docs/README.md) and any relevant file in [docs/output/](docs/output/) or [docs/reference/](docs/reference/). Check for relevant [rules](.cursor/rules/) and [skills](.cursor/skills/) when present.
2. **After completing tasks**: Consider whether docs, rules, or skills should be updated. Prefer updating `docs/` or `.cursor/rules/` over one-off long replies so future agents benefit.
3. **When adding behavior**: Prefer config and workspace over code changes in the core; document any necessary overrides in `docs/` so future merges are easier.

## Repo layout

| Area | Path | Notes |
|------|------|--------|
| **Core engine** | [nanobot/](nanobot/) | External community code. **Avoid editing** unless necessary; document changes in `docs/` for merge conflict resolution. |
| **Our layer** | [server/](server/), [frontend/](frontend/), [workspace/](workspace/) | Safe to extend. Config (e.g. `~/.nanobot/config.json`) drives workspace, MCP, and tool behavior. |
| **Context** | This file, [docs/](docs/), [.cursor/](.cursor/) | Cognitive framework, human/agent docs, Cursor rules and project skills. |

## Where to look

- **[docs/](docs/)** — Deep context: [docs/README.md](docs/README.md) (index), [docs/output/](docs/output/) (quick, human-oriented), [docs/reference/](docs/reference/) (full specs for agents).
- **[.cursor/rules/](.cursor/rules/)** — File-specific and global rules (always-apply and glob-scoped).
- **[.cursor/skills/](.cursor/skills/)** — Project skills (when to read CLAUDE.md, when to update docs).
- **[workspace/](workspace/)** — Nanobot runtime bootstrap (AGENTS.md, SOUL.md, USER.md, TOOLS.md, IDENTITY.md). When editing the repo, align with CLAUDE.md and docs.

## Merge-safety

- Prefer **config** (workspace path, MCP servers, tool_policy) and **workspace** bootstrap/skills over changing `nanobot/`.
- If you must change code under `nanobot/`, document what and why in `docs/reference/` so the next merge is easier.
- Extension points (no core edits required): [docs/output/extension-points.md](docs/output/extension-points.md).

## MCP and tools

- MCP servers are configured in `tools.mcp_servers` in config; tools are registered automatically.
- For **browser automation** (e.g. Playwright): see [docs/output/playwright-mcp.md](docs/output/playwright-mcp.md). Full MCP/tools reference: [docs/reference/mcp-and-tools.md](docs/reference/mcp-and-tools.md).
