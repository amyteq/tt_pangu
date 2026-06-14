# M9.4-T006: exit criteria validation + `docs/milestones/m9_4/final-review.md`

## Milestone
M9.4: Discovery / Debate Gate agents (planning + scaffolding).

## Goal
Roll up the M9.4 validation matrix into `docs/milestones/m9_4/final-review.md`,
update `PROJECT_STATE.md` and `docs/milestones/README.md` to reflect the new
"Discovery / Debate Gate" capability, then run the milestone-end
git+gh sequence per `docs/milestone-loop-protocol.md` §5.

## Read first

1. `docs/milestones/m9_4/loop-prompts.md`
2. `docs/tasks/m9_4/M9_4-T001..T005` closeouts
3. `docs/evidence/m9_4-kkr-replay/`
4. `docs/milestones/m9/final-review.md` — layout precedent
5. `docs/milestones/m8_5/final-review.md` — layout precedent
6. `docs/milestone-loop-protocol.md` §5 + new §7
7. `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md`
8. Skill: `milestone-final-review` (writes the canonical final-review doc)
9. Skill: `worktree-milestone-pr` (runs the §5 git+gh sequence)

## Scope

1. Run the `milestone-final-review` skill against the M9.4 validation
   matrix. Output: `docs/milestones/m9_4/final-review.md` mirroring the M8.5 / M9
   layout (acceptance roll-up table, evidence links, PASS/FAIL/SKIP
   counts, follow-up issues).
2. Update `PROJECT_STATE.md`:
   - Mark M9.4 ✓ done in the completed-milestones list.
   - Append a short "Discovery / Debate Gate" capability blurb under
     "Current MVP boundary" (or whichever section is the right home —
     check the existing doc shape, don't guess).
   - Update the `_Last updated:_` date and any active-milestone field
     so the next session lands correctly.
3. Update `docs/milestones/README.md`:
   - Add a §M9.4 entry that links back to `docs/milestones/m9_4/loop-prompts.md`
     and `docs/milestones/m9_4/final-review.md`. The entry follows the M8.5
     format (Goal, task sequence table, exit criteria).
4. Update `README.md` current-milestone section ONLY if M9.4 is the
   active milestone at close time. If M10 is active in parallel,
   `README.md` stays on M10; surface that in the closeout.
5. Run the `worktree-milestone-pr` skill:
   - One commit per Loop Prompt (T001..T006) — default per protocol §5.
   - Push the worktree branch.
   - `gh pr create` against `main` with `docs/milestones/m9_4/final-review.md` as
     the PR body and the `.github/pull_request_template.md` checklist
     completed (tests/docs/evidence/schema/remote).

## Non-goals

- Do not merge the PR. `gh pr merge` requires explicit human approval
  per protocol §5.
- Do not retroactively widen scope. If M9.4 missed something, file a
  follow-up issue, do not patch it under the final-review banner.
- Do not modify M9 / M10 final-review docs.

## Acceptance criteria

- `docs/milestones/m9_4/final-review.md` exists; layout matches M8.5 / M9; every
  acceptance criterion from T001..T005 is mapped to evidence (file
  path, test output, transcript link).
- `PROJECT_STATE.md` reflects M9.4 done.
- `docs/milestones/README.md` has a §M9.4 entry.
- `README.md` is correct for the active milestone at close time
  (M9.4 vs M10).
- One commit per Loop Prompt landed; the worktree branch is pushed;
  a PR is open against `main` with the final-review as the body and
  the PR template's checklist completed.
- All baseline validation still passes (pytest no-db; ruff; pnpm
  where applicable). The `tests/test_m9_4_agents.py` smoke suite from
  T005 passes in CI.
- No file outside the allowed set (final-review, PROJECT_STATE,
  milestones, README) is touched in T006.

## Permissions

- Local writes to `docs/milestones/m9_4/final-review.md`, `PROJECT_STATE.md`,
  `docs/milestones/README.md`, optionally `README.md`.
- `git add` / `git commit` / `git push` for the worktree branch are
  allowed under protocol §5.
- `gh pr create` is allowed; `gh pr merge` is NOT.
- No DB, no Kaggle, no network calls beyond `git push` / `gh pr create`.

## Closeout format

```
M9.4-T006 closeout
  docs/milestones/m9_4/final-review.md written (counts: PASS=… SKIP=… FAIL=…)
  PROJECT_STATE.md updated: YES | NO
  docs/milestones/README.md §M9.4 added: YES | NO
  README.md current-milestone: M9.4 | unchanged (M10)
  Commits landed (one per Loop Prompt): 6 | …
  Branch pushed: <branch-name>
  PR URL: <gh pr create url>
  CI status at close: pending | green | red
  Acceptance: PASS | FAIL
  Risks / blockers: …
  Next: human review + merge approval
```

## Stop condition

Stop after 60 turns. If CI on the PR fails for a reason not introduced
by M9.4, halt and ask — do not absorb unrelated repair work into the
M9.4 PR.
