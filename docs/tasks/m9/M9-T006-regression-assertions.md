# M9-T006: Regression assertions for CV + LB

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Encode the M9 regression thresholds as machine-checkable assertions
that read the recorded metrics from `runs` / `submissions` (no
re-training, no re-submitting).

This task assumes **M9-T002, M9-T004, M9-T005 closeouts are PASS**.

## Read first

1. M9-T002, M9-T004, M9-T005 closeouts
2. `tests/test_m*_smoke.py` (style precedent)
3. `tools/kca/db.py` (read helpers)
4. `docs/milestones/README.md` §M9 exit criteria

## Scope

1. Add a fixture (in `tests/fixtures/`, or inline in
   `tests/test_m9_smoke.py`) that reads the two runs by name
   (`baseline-lr`, `hgb-fe-v1`) and their CV metric, plus the
   `submissions` row's `public_score`.
2. Assertions:
   - `cv_lr >= 0.78`
   - `cv_hgb >= 0.80`
   - `cv_hgb > cv_lr` (HGB beat LR on the same CV split)
   - `submissions.public_score IS NOT NULL` for the M9-T004 row
3. Mark the assertion test as `@pytest.mark.skipif(not SUPABASE_DB_URL)`
   so the no-DB CI job skips cleanly. The live-DB CI job runs it.

## Non-goals

- Do not re-train. This is a regression-against-recorded-metrics test.
- Do not re-submit. The LB score is read from the existing
  `submissions` row.
- Do not change the LR or HGB code from M9-T002 / M9-T005.

## Acceptance criteria

- `python -m pytest tests/test_m9_smoke.py -v` passes when DB is
  reachable and the runs exist.
- `python -m pytest tests/test_m9_smoke.py -v` SKIPs (not FAILs) when DB
  is not reachable.
- All baseline validation still passes (pytest, ruff, pnpm).

## Permissions

- DB read requires `dangerouslyDisableSandbox=true`.
- `git commit` / `git push` deferred to milestone closeout.

## Closeout format

```
M9-T006 closeout
  cv_lr=<value>   threshold ≥ 0.78   PASS | FAIL
  cv_hgb=<value>  threshold ≥ 0.80   PASS | FAIL
  cv_hgb > cv_lr: YES | NO
  submissions.public_score for baseline run: <value> (PASS | FAIL)
  Acceptance: PASS | FAIL — link to issue
  Next: M9-T007 ready to start
```

## Stop condition

Stop after 60 turns. If any assertion FAILs, halt and open a follow-up
issue — do not silently lower the threshold.
