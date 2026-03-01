---
name: update-docs-after-change
description: After completing a feature or refactor, checks if docs need updates and proposes edits. Use when finishing a significant change so docs stay accurate for future agents and merges.
---

# Update docs after change

When you complete a feature or refactor:

1. **Check** whether [docs/reference/](../../../docs/reference/) or [docs/output/](../../../docs/output/) should be updated (e.g. new extension point used, new API, changed behavior).
2. **Propose edits** to the relevant doc files if needed. Do not edit core under `nanobot/`; only suggest changes to `docs/` (and optionally `.cursor/rules/` or CLAUDE.md if the cognitive framework should change).
3. If you had to **edit files under `nanobot/`**, add or update a short note in `docs/reference/` describing what was changed and why, to ease future merge conflict resolution.
