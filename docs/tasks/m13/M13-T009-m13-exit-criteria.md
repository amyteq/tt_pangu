# M13-T009: M13 exit criteria validation + `docs/milestones/m13/final-review.md`

## Milestone
M13: evaluation, reliability, and regression suite.

## Goal
Run the M13 validation matrix end-to-end; write
`docs/milestones/m13/final-review.md` mirroring the M9 / M10 layout. After
the review doc is written, invoke `worktree-milestone-pr` to
commit per Loop Prompt, push the worktree branch, and open the
final M13 PR against `main`.

This task assumes **all of M13-T000 through M13-T008 closeouts
are PASS**.

## Read first

1. All M13 closeouts (T000–T008).
2. `docs/milestones/m10/final-review.md` (most recent layout precedent).
3. `docs/milestones/m9/final-review.md` (layout precedent).
4. `docs/milestones/m8_5/final-review.md` (layout precedent).
5. The `milestone-final-review` skill SKILL.md.
6. The `worktree-milestone-pr` skill SKILL.md.

## Scope

1. **Validation matrix.** Re-verify the evidence from each Loop
   Prompt's closeout still holds:
   - T000: ADR-0019 + architecture doc exist; 3 discovery
     transcripts (or 2 + greenfield SKIP-NOTE) under
     `docs/evidence/m13/T000/discovery/`; canonical acceptance
     lines verified.
   - T001: migration 0010 applied; 7 DB helpers; `kca eval` 4
     verbs; `NO_SUITES_REGISTERED` refusal still works for the
     empty case.
   - T002: `tool-smoke` registered; ≥10 cases; audit-grep clean.
   - T003: three Kaggle replays registered; fixtures committed;
     deterministic.
   - T004: `kernel-dryrun` registered; 4 cases; credentials-gate
     refusal verified; audit-grep clean.
   - T005: `reasoning` registered; 5–10 cases; deterministic
     check + (optional) rubric.
   - T006: route enum wired; refusal logic verified; the
     `--route-compare` mocked-only run produces 25 rows.
   - T007: `kca eval report --json | --md`; sample report under
     `runs/m13-eval/<timestamp>/` committed.
   - T008: `tests/test_m13_smoke.py` + `tests/test_m13_e2e.py`
     PASS; `.github/workflows/eval.yml` validated; tracking
     issue exists; issue #11 still CLOSED.

2. **Full pytest + ruff posture.**
   - `pytest tests/ services/decision_api/tests` — expect 0 new
     failures vs the LP8 baseline.
   - `ruff check .` clean.
   - `ruff format --check .` clean.
   - pnpm UI gates — SKIP if pnpm not on PATH (M13 did not
     modify `ui/`; CI is authoritative).

3. **`kca eval` cross-checks.**
   - `kca eval list --json` shows ≥5 suites
     (tool-smoke, kaggle-replay-titanic,
     kaggle-replay-spaceship-titanic, kaggle-replay-house-prices,
     kernel-dryrun, reasoning).
   - `kca eval run --all --route mocked --dry-run --json` exits
     0 and produces ≥1 row per registered suite.
   - `kca eval report --md` against the latest run reproduces a
     diff-clean Markdown report.

4. **Write `docs/milestones/m13/final-review.md`** via the
   `milestone-final-review` skill. Mirror the M10 layout:
   header / summary / exit-criteria-met header / validation
   matrix table / deviations / what landed / follow-ups for the
   next milestone.

5. **Update tracking docs.**
   - `PROJECT_STATE.md` — bump current milestone to M14
     (whatever the next milestone is at that point — likely
     M11 if CTF was prioritised over M13). Refresh the
     cross-cutting follow-ups summary.
   - `README.md` — current-milestone block; bump product-plan
     range if it changes.
   - `docs/milestones/README.md` — mark M13 `✓ done` with the
     validation matrix tally + the recorded report path.
   - `docs/milestones/m13/handoff.md` — new file mirroring
     `docs/milestones/m10/handoff.md`.

6. **Invoke `worktree-milestone-pr`.** Per protocol §5 default:
   - One commit per Loop Prompt on the worktree branch.
   - Push the worktree branch.
   - Open a PR against `main` using `docs/milestones/m13/final-review.md`
     as the body.
   - Do NOT auto-merge; the PR needs human approval per the
     engineering-practice routing rules.

## Non-goals

- Do not modify any source code (`src/`, `tools/`, `services/`,
  `tests/`, `ui/`, `supabase/migrations/`) in this Loop Prompt.
  T009 is for review docs + commit/push/PR only. If a regression
  is found, re-open the relevant prior Loop Prompt — don't
  patch from T009.
- Do not auto-merge the PR.
- Do not close M11 / M12 follow-ups unless their own PRs have
  merged. (CTF / hackathon eval cases were explicitly deferred
  to M13.1 / M13.2; document the deferral, do not promote it.)

## Acceptance criteria

- `docs/milestones/m13/final-review.md` exists; layout matches M9 / M10;
  the validation matrix has 0 FAIL rows.
- `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md`, and
  `docs/milestones/m13/handoff.md` are updated consistently.
- The PR is open against `main` with the final-review doc as
  the body.
- pytest + ruff posture is at-or-better than the LP8 baseline.
- No new commits to `main` directly; everything goes through
  the PR.
- Two follow-up issues filed: `M13.1 — CTF / lab eval cases
  (gated on M11)` and `M13.2 — hackathon / Devpost eval cases
  (gated on M12)`. Each labelled `type:feature`, `area:eval`,
  `decision:needed`.

## Permissions

- `git commit` per Loop Prompt — ALLOWED at this prompt.
- `git push` of the worktree branch — ALLOWED.
- `gh pr create` — ALLOWED.
- `gh issue create` for the M13.1 / M13.2 follow-ups — ALLOWED.
- `gh pr merge` — NOT ALLOWED. Requires human approval.
- Direct push to `main` — NOT ALLOWED.

## Closeout format

```
M13-T009 closeout
  Validation matrix: <N> PASS / <M> SKIP / 0 FAIL
  docs/milestones/m13/final-review.md: written (mirrors M9 / M10 layout; <N>-check matrix)
  PROJECT_STATE.md: updated; current milestone bumped from M13 to <next>
  README.md: current-milestone pointer bumped from M13 to <next>
  docs/milestones/README.md: M13 marked ✓ done with per-task result table
  docs/milestones/m13/handoff.md: written (mirrors m10-handoff.md)
  Deferred-scope follow-ups filed: M13.1 (<url>), M13.2 (<url>)
  PR url: <link>
  Acceptance: PASS — milestone closeout artifacts complete
  Next: <next milestone> (per PROJECT_STATE.md update)
```

## Related issues

- M13 proposal issue — closes on the M13 PR merge.
- M13.1 / M13.2 follow-ups — filed at this prompt; stay
  `decision:needed` until M11 / M12 land.

## Stop condition

Stop after 60 turns. If the validation matrix surfaces a FAIL
on any prior Loop Prompt's evidence, HALT — re-open the
relevant prior Loop Prompt, fix, re-run; do NOT write the final
review until the matrix is clean.
