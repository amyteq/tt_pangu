---
name: worktree-milestone-pr
description: Execute the milestone-end git+gh sequence per docs/milestone-loop-protocol.md §5 — one commit per Loop Prompt, push the worktree branch, open a PR against main. Use only after docs/milestones/m{N}/final-review.md is written.
---

# worktree-milestone-pr — milestone-end commit/push/PR

Use this skill at the very end of a milestone, after `docs/milestones/m{N}/final-review.md` has been written, to commit per Loop Prompt, push the worktree branch, and open a PR against `main`.

This skill encodes protocol §5 (Git / GitHub — worktree mode) so loop prompts and the closeout agent don't have to re-derive the sequence.

## Pre-flight gate

Refuse to proceed if any of the following is false:

1. Inside a git worktree branched off `main`:
   ```bash
   git rev-parse --is-inside-work-tree
   git rev-parse --abbrev-ref HEAD            # not "main"
   git merge-base --is-ancestor main HEAD     # main is ancestor of HEAD
   ```
2. `docs/milestones/m{N}/final-review.md` exists and is non-empty.
3. `git status` shows only milestone-owned files (compare against the union of "files changed" sections in `docs/tasks/m{N}/M{N}-T*-*.md`). If anything else shows up, halt and ask.

## Commit sequence (default: one commit per Loop Prompt)

For each Loop Prompt `N` in `docs/milestones/m{N}/loop-prompts.md`, in order:

1. Stage only files in that prompt's scope (`git add <paths>`).
2. Commit with message:
   ```
   M{N}-T{NNN}: <one-line summary from the task spec's Goal>

   <2-3 lines from the Loop Prompt's Closeout report>
   ```
3. Move to the next Loop Prompt.

Final commit:

```
M{N}: final review

See docs/milestones/m{N}/final-review.md.
```

Squash variant (only if the milestone's last task spec or the user explicitly requested it):

```
M{N}: <milestone title> (squash)

<key bullets from docs/milestones/m{N}/final-review.md "What landed">
```

## Push and PR

```bash
git push -u origin <branch>

gh pr create --base main --head <branch> \
  --title "M{N}: <milestone title>" \
  --body-file docs/milestones/m{N}/final-review.md
```

If the milestone is planning-only (e.g. M8.5-T003), prefix the PR title with `[planning]` and add `(no code changes)` if applicable.

## What this skill must NOT do

- No `git push --force`, ever.
- No `gh pr merge` **from this skill** — a milestone PR is merged by the human. (Deliberately stricter than the repo-wide dev-phase policy, which auto-allows `gh pr merge`; this is a scope rule for this skill, not a claim about the repo.)
- No push to `main` directly.
- No `gh label create/edit/delete` against existing labels or `gh issue edit/comment` / `gh pr edit/comment` against issues/PRs not owned by this milestone — those stay on ASK per protocol §5.
- No commits that touch files outside the milestone's scope.

## Output

Print:
- Branch name.
- Ordered commit SHAs and titles.
- Push status (new branch vs fast-forward).
- PR URL.

If any step is blocked, halt and ask before improvising.
