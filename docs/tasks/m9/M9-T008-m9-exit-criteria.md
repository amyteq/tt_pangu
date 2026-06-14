# M9-T008: M9 exit criteria + `docs/milestones/m9/final-review.md`

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Validate every M9 acceptance criterion, write `docs/milestones/m9/final-review.md`
using the `milestone-final-review` skill (mirroring the M8 / M8.5
layout), and use `worktree-milestone-pr` to commit per-Loop-Prompt,
push the worktree branch, and open the final M9 PR against `main`.

This task assumes **M9-T000 through M9-T007 closeouts are all PASS**.

## Read first

1. All M9 closeouts (T000–T007)
2. `docs/milestones/m8/final-review.md` (precedent)
3. `docs/milestones/m8_5/final-review.md` (precedent)
4. `.claude/skills/milestone-final-review/SKILL.md`
5. `.claude/skills/worktree-milestone-pr/SKILL.md`
6. `docs/milestone-loop-protocol.md` §5

## Scope

1. Run the full validation suite locally:
   - `python -m pytest tests/ services/decision_api/tests -v`
   - `ruff check .` and `ruff format --check .`
   - `pnpm -C ui install --frozen-lockfile`
   - `pnpm -C ui lint`, `typecheck`, `build`
   - `pnpm -C ui run test --run`
   - `python -m pytest tests/test_m9_e2e.py -v` (no-DB) and (if DB
     reachable) `tests/test_m9_smoke.py`
2. Confirm via DB queries / `kca run list` that:
   - the M9 baseline run has a CV metric;
   - the M9 hgb-fe-v1 run has a CV metric;
   - the M9-T004 submissions row has a public LB score.
3. Update `PROJECT_STATE.md` to record M9 completion and point to M10
   (CTF workflow) or the next priority.
4. Update `README.md` (if it lists current milestones).
5. Update `docs/milestones/README.md` if any planned capability changed during
   M9.
6. Append `docs/milestones/m9/handoff.md` mirroring `m8-handoff.md`.
7. Call `milestone-final-review` to produce `docs/milestones/m9/final-review.md`.
8. Call `worktree-milestone-pr` to commit + push + open the M9 PR.

## Non-goals

- Do not start M10.
- Do not run another Kaggle submit.
- Do not change CI workflows (the test job already covers the M9 tests).
- Do not invent new metrics that weren't recorded by T000–T007.

## Acceptance criteria

- Every check in M9-T000 through M9-T007's acceptance lists is mapped
  to evidence in `docs/milestones/m9/final-review.md`.
- `docs/milestones/m9/final-review.md` exists, matches the M8 / M8.5 layout, and
  reports PASS on every non-SKIP check.
- `PROJECT_STATE.md` says M9 is complete.
- `docs/milestones/m9/handoff.md` exists.
- The M9 PR is open against `main` with the closeout pasted into the
  PR body using the PR template.
- All validation passes.

## Permissions

- Local file edits allowed.
- DB read requires `dangerouslyDisableSandbox=true`.
- `git commit`, `git push`, `gh pr create` are explicitly authorized in
  this Loop Prompt only (override of protocol §5 for milestone closeout).
- `gh pr merge` is NOT authorized — merge is a human decision.

## Closeout format

```
M9-T008 closeout
  Validation matrix: <n> PASS / <m> SKIP / 0 FAIL
  docs/milestones/m9/final-review.md: written (<n> lines)
  PROJECT_STATE.md: updated to M9 complete / M10 next
  docs/milestones/m9/handoff.md: written
  PR url: https://github.com/amyteq/tt_pangu/pull/<n>
  Acceptance: PASS — milestone closeout complete
  Next: M10 (CTF workflow) is now unblocked
```

## Stop condition

Stop after 60 turns. If any acceptance criterion across T000–T007 is
GAP or FAIL, halt and open a follow-up issue — do NOT mark M9 complete
to "make the milestone exit".
