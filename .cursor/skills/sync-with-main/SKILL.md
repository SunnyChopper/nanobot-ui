---
name: sync-with-main
description: Sync local branch with origin/main via stash–pull–reapply; write and use merge-context docs under .claude/merges/ for conflict resolution. Use when the user asks to sync with main, pull latest, stash and pull, reapply changes, or resolve merge conflicts after pulling.
---

# Sync with main (stash–pull–reapply)

Use this workflow when the user wants to get the latest changes from `main` while preserving local or uncommitted work, or when resolving merge conflicts after a pull.

## When to use

- User says: sync with main, pull latest, stash and pull, reapply my changes, or resolve merge conflicts after pulling.
- For the full step-by-step checklist, use the project command in [.cursor/commands/sync-main.md](../../commands/sync-main.md).

## Workflow (short)

1. **Capture context** — If there are uncommitted or local changes, write a merge-context doc under `.claude/merges/` (see [reference.md](reference.md) for the template). Name it e.g. `YYYY-MM-DD-sync-main.md` or `YYYY-MM-DD-HHMM-sync-main.md`.
2. **Stash** — `git stash push -u -m "sync-main YYYY-MM-DD"` so untracked files are included.
3. **Pull** — `git fetch origin main` then `git merge origin/main`. If conflicts, resolve using the latest `.claude/merges/*.md` (Intent + Areas changed and why).
4. **Reapply** — `git stash pop`. If conflicts, resolve again using the same merge-context doc.

## Conflict resolution

Whenever merge or stash-pop reports conflicts:

- Open the **most recent** file in `.claude/merges/` (sort by name descending).
- Read "Intent" and "Areas changed and why."
- Resolve each conflicted file so upstream is kept except where it would break that intent.
- Add a "Resolution notes" section to that file for any non-obvious choices.

## Merge-context template

See [reference.md](reference.md) for the full template and field meanings.
