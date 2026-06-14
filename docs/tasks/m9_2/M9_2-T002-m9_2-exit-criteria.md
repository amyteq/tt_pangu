# M9.2-T002: M9.2 exit criteria + final review + PR

## Milestone
M9.2: `/save-log` skill — Claude Code session transcript export.

## Goal
Validate the full M9.2 acceptance matrix, write
`docs/milestones/m9_2/final-review.md` via the `milestone-final-review` skill,
update `docs/milestones/README.md` / `PROJECT_STATE.md` / `README.md`, write
`docs/milestones/m9_2/handoff.md`, then call the `worktree-milestone-pr`
skill to commit per-Loop-Prompt, push the worktree branch, and open the
M9.2 PR against `main`.

## Read first

1. `docs/tasks/m9_2/M9_2-T000-save-log-scaffold-and-impl.md` + closeout.
2. `docs/tasks/m9_2/M9_2-T001-save-log-smoke-and-docs.md` + closeout.
3. `docs/milestones/m9/final-review.md` — layout precedent (executable milestone).
4. `docs/milestones/m8_5/final-review.md` — layout precedent (planning-mixed
   milestone).
5. `docs/milestones/m9/handoff.md` — handoff template precedent.
6. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
7. `docs/milestones/README.md` — current shape; locate the M9.2 section
   inserted between M9 and M10.
8. `PROJECT_STATE.md` — current-milestone block.
9. `README.md` — current-milestone block + tooling section.
10. `.claude/skills/milestone-final-review/SKILL.md` (or equivalent).
11. `.claude/skills/worktree-milestone-pr/SKILL.md`.

## Scope

1. **Validation matrix.** Re-run the cross-task acceptance checks:
   - `ruff check scripts/save_claude_session_log.py` — clean.
   - `ruff format --check scripts/save_claude_session_log.py` — clean.
   - `python scripts/save_claude_session_log.py --help` — exits 0,
     prints the four flags.
   - `python -m pytest tests/ -q` — green.
   - `git status` shows only files owned by this milestone (T000 +
     T001 + T002 additions). If anything else surfaces, halt and ask.
   - The export from T001 (`docs/logs/<name>.md`) still exists and
     is well-formed. Decide per-export whether it gets committed —
     default is to **not** commit transcripts produced for smoke
     unless they are evidentially load-bearing for the milestone
     review.

2. **Final review doc.** Invoke `milestone-final-review` (or write by
   hand if the skill is unavailable) to produce
   `docs/milestones/m9_2/final-review.md`. Mirror the M9 / M8.5 layout:
   - Header summary: ship date, one-paragraph "what landed".
   - Per-task validation table with PASS/FAIL/SKIP, evidence link,
     and notes for each of T000 / T001 / T002.
   - "What landed" bullet list with the three new files + README +
     milestones / PROJECT_STATE updates.
   - "Risks / known limitations" — at minimum: `uvx` dependency,
     unknown frontmatter keys, secret-pattern conservatism.
   - "Follow-ups" — link any issues filed during T000 / T001.
   - Final PASS count.

3. **Update `docs/milestones/README.md`.** Flip the M9.2 entry from "in
   planning" to "✓ done" with a one-line summary of what landed
   (skill + script + docs/logs/ + smoke evidence). Keep the M9.2
   section between M9 and M10. Do not renumber M10–M13.

4. **Update `PROJECT_STATE.md`.** Set the current milestone back to
   M10 (since M9.2 is now done) with a brief note that M9.2 closed
   the operator-tooling gap and `/save-log` is now available. Update
   "open decisions" / "blockers" only if a real follow-up surfaced.

5. **Update `README.md`.** Update the current-milestone block to
   point at M10 again. Keep the `/save-log` line that T001 added; if
   T001 forgot, add it here (one line, no more).

6. **Write `docs/milestones/m9_2/handoff.md`.** Use
   `docs/milestones/_templates/handoff-prompt.md` as the template. Populate:
   - "State at handoff": M9.2 done; skill + script landed.
   - "Read these files first": `docs/milestones/m9_2/final-review.md`, the M9.2
     loop prompts, `.claude/skills/save-log/SKILL.md`, the script,
     and the M10 read list (since M10 is the next active milestone).
   - "Current task": resume / start M10 per `docs/milestones/m10/loop-prompts.md`.

7. **Commit + push + PR via `worktree-milestone-pr`.** Pre-flight
   gate checks (per the skill's `Pre-flight gate` section):
   - Inside a worktree branched off `main`.
   - `docs/milestones/m9_2/final-review.md` exists and is non-empty.
   - `git status` shows only milestone-owned files.

   Then commit one commit per Loop Prompt (default), push the
   worktree branch with `-u`, and open the PR:

   ```bash
   git push -u origin worktree-m9_2-planning   # or whichever branch the worktree is on

   gh pr create --base main --head worktree-m9_2-planning \
     --title "M9.2: /save-log skill — Claude Code session transcript export" \
     --body-file docs/milestones/m9_2/final-review.md
   ```

   Record the PR URL in the closeout. Do **not** `gh pr merge`. Do
   **not** push to `main`.

## Non-goals

- Do not change `scripts/save_claude_session_log.py` after T000 unless
  fixing a bug surfaced by step 1's validation matrix. Substantive
  behavioural changes belong in a follow-up PR.
- Do not run `gh pr merge`, `git push --force`, `git push -f`, or any
  push to `main` directly.
- Do not delete the worktree until the PR is open (and even then,
  default is to keep it for audit; see `worktree-milestone-pr` skill).
- Do not promote `docs/logs/*.md` into Supabase or any artifact-storage
  table — that is an explicit out-of-scope follow-up.
- Do not add new task specs to M9.2.

## Acceptance criteria

- All T000 + T001 acceptance criteria still hold (re-verified in step
  1).
- `docs/milestones/m9_2/final-review.md` exists, follows the M9 / M8.5 layout,
  and lists T000 / T001 / T002 with PASS/FAIL/SKIP plus evidence.
- `docs/milestones/README.md` shows M9.2 as `✓ done` with a one-line summary.
- `PROJECT_STATE.md` current-milestone block names M10 again.
- `README.md` current-milestone block names M10 again; `/save-log`
  is mentioned exactly once in the file.
- `docs/milestones/m9_2/handoff.md` exists, follows
  `docs/milestones/_templates/handoff-prompt.md`'s shape.
- One commit per Loop Prompt landed on the worktree branch
  (`M9.2-T000:`, `M9.2-T001:`, `M9.2-T002:`, plus the
  `M9.2: final review` commit if the skill's default applies — or
  one squash commit if the milestone reviewer opts for it).
- `git push -u origin <branch>` succeeded.
- `gh pr create` produced a PR URL against `main`. The PR body is
  `docs/milestones/m9_2/final-review.md` and the engineering-practice template
  checklist is filled.

## Permissions

- Local file writes inside the worktree are allowed.
- Non-destructive GitHub writes are allowed per CLAUDE.md dev-phase
  carve-out: `gh pr create`, `gh issue create|edit|comment|close`,
  `gh label create|edit|clone`, `git push` of new commits.
- Force-push, `gh pr merge`, push to `main`, `gh issue delete`,
  `gh release delete`, `gh repo delete`, `gh secret delete`, and any
  rebase that rewrites already-pushed history are **not** allowed.
- Reads of `.env*`, `~/.kaggle/kaggle.json`, `~/.ssh/**`,
  `~/.aws/**`, `~/.config/gcloud/**`, `~/.config/gh/**`, and
  `secrets/**` are not required and not performed.
- No DB calls; no `dangerouslyDisableSandbox`.

## Closeout format

```
M9.2-T002 closeout
  Validation matrix: PASS (ruff / --help / pytest / git status clean)
  docs/milestones/m9_2/final-review.md: written (lines=<N>, PASS=<count>, FAIL=<count>, SKIP=<count>)
  docs/milestones/README.md: M9.2 marked ✓ done (one-line summary present)
  PROJECT_STATE.md: current-milestone → M10
  README.md: current-milestone → M10; /save-log mention present
  docs/milestones/m9_2/handoff.md: written
  Commits on worktree branch: <N> commits, ordered per Loop Prompts
  git push -u origin <branch>: PASS
  PR URL: <url>
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M9.2 complete; resume M10 per docs/milestones/m10/loop-prompts.md
```

## Related issues

- N/A — file an M9.2-T002 issue when picking up. Link the M9.2 PR
  back to the M9.2 issues (T000, T001, T002) in the PR body via
  "Closes #…".

## Stop condition

Stop after 60 turns. Halt and ask if:

- The validation matrix in step 1 surfaces a regression (e.g. ruff
  starts failing after a rebase). Fix the root cause; do not skip
  the check.
- `git status` shows files outside the M9.2 scope. Halt and ask
  before any commit.
- `gh pr create` fails with an authentication error (the dev-phase
  carve-out assumes `gh auth status` is green). Halt — do not read
  `~/.config/gh/hosts.yml` directly.
- The `worktree-milestone-pr` skill refuses pre-flight (e.g.
  `docs/milestones/m9_2/final-review.md` missing). Diagnose and rerun — do not
  bypass the skill's gate.
