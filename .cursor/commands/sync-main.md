# Sync with main (stash–pull–reapply)

Run the full stash–pull–reapply workflow to get the latest changes from **`upstream/main`** (the original upstream repo), with context offloading so merge conflicts can be resolved using the purpose of your local changes.

**Setup:** Ensure the `upstream` remote points to the source repo (e.g. the original `nanobot` repo). Your fork is `origin`; you pull from `upstream` and push to `origin`.

You may add extra context after the command (e.g. `/sync-main focus on keeping the new desktop tool changes`). Use that context when writing the merge-context doc and when resolving conflicts.

## Workflow

Follow these steps in order.

### 1. Check state

Run `git status`. If the working tree is clean and the branch is already up to date with `upstream/main`, report "Already up to date" and stop. Otherwise continue.

### 2. Capture context (if there are uncommitted or local changes)

If there are uncommitted changes (staged or unstaged) or local commits not on `upstream/main`:

- Create the directory `.claude/merges/` if it does not exist.
- Create or update a merge-context file there. Name it by date (and optionally time) so each sync has a traceable doc, e.g.:
  - `YYYY-MM-DD-sync-main.md`, or
  - `YYYY-MM-DD-HHMM-sync-main.md` for multiple syncs per day.

Use this template and fill it from `git status`, `git diff`, `git diff --staged`, and `git log` so the doc explains the **purpose** of the local work:

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
| (path) | (why) |

## Decisions to preserve
- Any convention or decision that upstream might not have (so we keep it in conflicts).
```

### 3. Stash

Run:

```bash
git stash push -u -m "sync-main YYYY-MM-DD"
```

Use the same date (and time if you used it in the filename). `-u` includes untracked files so nothing is lost.

### 4. Pull main from upstream

Run:

```bash
git fetch upstream main
git merge upstream/main
```

- If the merge completes with no conflicts, go to step 5.
- If there are merge conflicts: open the **most recent** file in `.claude/merges/` (e.g. sort by name descending), read the "Intent" and "Areas changed and why" sections, resolve each conflicted file so upstream is kept except where it would break that intent, then run `git add` on the resolved files and complete the merge. Optionally add a short "Resolution notes" section to that merge-context file for non-obvious choices.

### 5. Reapply stash

Run:

```bash
git stash pop
```

- If there are no conflicts, the workflow is done. Optionally add a "Resolved on YYYY-MM-DD" note at the top of the merge-context file.
- If there are conflicts: again open the most recent `.claude/merges/*.md`, use "Intent" and "Areas changed and why" to resolve each conflicted file, then `git add` and continue until the working tree is clean. Document any non-obvious resolution choices in that file.

## Conflict resolution rule

Whenever `git status` or the merge or stash pop reports conflicts:

1. Open the latest `.claude/merges/*.md` (e.g. list the directory and pick the most recent by name).
2. Read "Intent" and "Areas changed and why."
3. Resolve each conflicted file so that upstream changes are kept **except** where they would violate the stated intent.
4. Document non-obvious choices in a "Resolution notes" section in the same file.
