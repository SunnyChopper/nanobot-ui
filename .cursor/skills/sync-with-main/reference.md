# Merge-context template (reference)

Use this when writing a new file under `.claude/merges/` before stashing. Fill it from `git status`, `git diff`, `git diff --staged`, and `git log` so the doc explains the **purpose** of the local work. During conflict resolution, the agent reads "Intent" and "Areas changed and why" to decide how to merge.

## Template

```markdown
# Merge context: sync with main — YYYY-MM-DD

## Summary
One-paragraph summary of what the local branch / uncommitted work is for.

## Intent (what to preserve when resolving conflicts)
- Goal 1: ...
- Goal 2: ...

## Areas changed and why
| Path / area | Purpose of change |
|-------------|-------------------|
| nanobot/agent/... | ... |
| server/... | ... |

## Decisions to preserve
- Convention or decision that upstream might not have (so we keep it in conflicts).
```

## Naming

- One file per sync: `YYYY-MM-DD-sync-main.md` or `YYYY-MM-DD-HHMM-sync-main.md` for multiple syncs per day.
- The directory `.claude/merges/` is local-only (typically in `.gitignore`); merge-context docs are for conflict resolution on this machine.

## After resolving conflicts

Optionally add at the top of the same file: "Resolved on YYYY-MM-DD." For non-obvious choices, add a "Resolution notes" section.
