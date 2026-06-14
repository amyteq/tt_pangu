# M10-T008: M10 exit criteria validation + `docs/milestones/m10/final-review.md`

## Milestone
M10: live end-to-end regression test — Petals to the Metal.

## Goal
Run the M10 validation matrix end-to-end and write
`docs/milestones/m10/final-review.md` mirroring the M8 / M8.5 / M9 layout. After
the review doc is written, invoke `worktree-milestone-pr` to commit
per-Loop-Prompt, push the worktree branch, and open the final M10 PR
against `main`.

This task assumes **all of M10-T000 through M10-T007 closeouts are
PASS**.

## Read first

1. All M10 closeouts (T000–T007).
2. `docs/milestones/m9/final-review.md` (the most recent layout precedent).
3. `docs/milestones/m8_5/final-review.md` (layout precedent).
4. `docs/milestones/m8/final-review.md` (layout precedent).
5. The `milestone-final-review` skill SKILL.md.
6. The `worktree-milestone-pr` skill SKILL.md.

## Scope

1. **Validation matrix.** Read each Loop Prompt's closeout from
   scrollback / Git history and re-verify the evidence still holds:
   - M10-T000: credentials reachable; competition row exists.
   - M10-T001: `data/tpu-getting-started/manifest.json` staged; raw
     TFRecords not staged.
   - M10-T002: baseline notebook + kernel-metadata.json present;
     `experiment_runs` row with local metric.
   - M10-T003: `agent_reviews` + `human_decisions` rows with
     `target_op="kernel_push"`; approved.
   - M10-T004: single real `kaggle kernels push`; kernel run
     `complete`; `submissions` row with non-null `public_score`.
   - M10-T005: second `experiment_runs` row; alt-axis metric.
   - M10-T006: `tests/test_m10_smoke.py` PASS with DB; SKIP without.
   - M10-T007: `tests/test_m10_e2e.py` PASS dry-run; audit-grep guard
     PASS; issue #11 CLOSED.

2. **Full pytest + ruff posture.**
   - `pytest tests/ services/decision_api/tests` — expect 0 new
     failures vs the LP7 baseline.
   - `ruff check .` clean.
   - `ruff format --check .` clean.
   - pnpm UI gates (lint / typecheck / build / vitest) — run if pnpm
     is on PATH; SKIP otherwise (CI is authoritative).

3. **`kca run list` cross-check.**
   `kca run list --competition tpu-getting-started --json` should
   show both runs (baseline + alt) with recorded metrics and tags;
   M10-T004's `submissions` row should appear in the related row(s).

4. **Write `docs/milestones/m10/final-review.md`** via the `milestone-final-
   review` skill. Mirror M9's structure: header / summary / exit-
   criteria-met header / validation matrix table / deviations /
   what landed / follow-ups for the next milestone.

5. **Update tracking docs.**
   - `PROJECT_STATE.md` — bump current milestone to M11 (CTF/lab);
     refresh the cross-cutting follow-ups summary (close any of
     A / C / D / E that landed during M10).
   - `README.md` — current-milestone block; bump product-plan
     range if it changes.
   - `docs/milestones/README.md` — mark M10 `✓ done` with the validation
     matrix tally + the recorded LB score.
   - `docs/milestones/m10/handoff.md` — new file mirroring
     `docs/milestones/m9/handoff.md`. Include any new cross-cutting
     items M10 surfaced.

6. **Invoke `worktree-milestone-pr`.** Per protocol §5 default:
   - One commit per Loop Prompt on the worktree branch.
   - Push the worktree branch.
   - Open a PR against `main` using `docs/milestones/m10/final-review.md` as the
     body.
   - Do NOT auto-merge; the PR needs human approval per the
     engineering-practice routing rules.

## Non-goals

- Do not modify any source code (`src/`, `tools/`, `services/`,
  `tests/`, `ui/`, `supabase/migrations/`) in this Loop Prompt. T008
  is for review docs + commit/push/PR only. If a regression is found,
  re-open the relevant prior Loop Prompt — don't patch from T008.
- Do not auto-merge the PR.
- Do not retire any issues except the M10 task issues (T000–T008).
  Issues #11, #14, #15, #16, #17 stay open unless their own work
  PRs have merged.

## Acceptance criteria

- `docs/milestones/m10/final-review.md` exists; layout matches M9 / M8.5; the
  validation matrix has 0 FAIL rows.
- `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md`, and
  `docs/milestones/m10/handoff.md` are updated consistently.
- The PR is open against `main` with the final-review doc as the body.
- pytest + ruff posture is at-or-better than the LP7 baseline.
- No new commits to `main` directly; everything goes through the PR.

## Permissions

- `git commit` per Loop Prompt — ALLOWED at this prompt.
- `git push` of the worktree branch — ALLOWED at this prompt.
- `gh pr create` — ALLOWED at this prompt.
- `gh pr merge` — NOT ALLOWED. Requires human approval.
- Direct push to `main` — NOT ALLOWED.

## Closeout format

```
M10-T008 closeout
  Validation matrix: <N> PASS / <M> SKIP / 0 FAIL
  docs/milestones/m10/final-review.md: written (mirrors M9 / M8.5 layout; <N>-check matrix)
  PROJECT_STATE.md: updated to M10 complete / M11 next; LR/HGB/LB snapshot recorded for M9 + baseline-tl/alt local + M10-T004 LB for M10
  README.md: current milestone pointer bumped from M10 (planned) to M11 (planned)
  docs/milestones/README.md: M10 marked ✓ done with full per-task result table
  docs/milestones/m10/handoff.md: written (mirrors m9-handoff.md)
  PR url: <link>
  Acceptance: PASS — milestone closeout artifacts complete
  Next: M11 (CTF/lab workflow) is the next planning milestone.
```

## Related issues

- #12 — M10 proposal. Closes on the M10 PR merge.
- #11, #14, #15, #16, #17 — parallel M9 follow-ups. T008 records
  which of them closed during M10 in the final-review doc; the rest
  stay open.

## Stop condition

Stop after 60 turns. If the validation matrix surfaces a FAIL on any
prior Loop Prompt's evidence, HALT — re-open the relevant prior
Loop Prompt, fix, re-run; do NOT write the final review until the
matrix is clean.
