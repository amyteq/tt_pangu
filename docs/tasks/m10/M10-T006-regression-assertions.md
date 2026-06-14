# M10-T006: Regression assertions for Petals to the Metal CV + LB

## Milestone
M10: live end-to-end regression test — Petals to the Metal.

## Goal
Add a DB-gated assertion test that pins the M10 evidence and codifies
the regression-floor checks. Failures here block M10 exit but do NOT
trigger another real Kaggle kernel push.

This task assumes **M10-T002, M10-T004, M10-T005 closeouts are PASS**.

## Read first

1. M10-T002, M10-T004, M10-T005 closeouts
2. `tests/test_m9_smoke.py` (the pattern — 4 DB-gated assertions)
3. `tests/test_m8_smoke.py` (the older DB-gated pattern)
4. `docs/tasks/m9/M9-T006-regression-assertions.md` (the precedent)

## Scope

Add `tests/test_m10_smoke.py` mirroring `tests/test_m9_smoke.py`:

1. Module-level skip when `SUPABASE_DB_URL` is unset (so the `no-db`
   CI job still runs the suite without failing).
2. Tests:
   - `test_baseline_local_metric_clears_floor` — baseline holdout
     accuracy ≥ TBD floor (e.g. ≥ 0.50 — well above random for a
     104-class task; final number lands in the test after M10-T002).
   - `test_alt_local_metric_clears_baseline_or_documents` — alt
     experiment ≥ baseline OR a `delta_note` field in
     `experiment_runs.analysis` documents the reason.
   - `test_real_push_lb_recorded` — `submissions` row exists for the
     M10-T004 push with non-null `public_score` (or `public_lb_score`
     if issue #17 has landed).
   - `test_kernel_push_event_recorded` — `agent_job_events` has a row
     with the worker's `kernel_push`-related event literals.

3. Each assertion queries the local supabase-db directly (psycopg or
   the same helper M9 used). No HTTP layer dependency, no test
   fixtures that require Kaggle network access.

## Non-goals

- Don't add new tests that require real Kaggle network access (T007
  is the dry-run e2e test).
- Don't change `services/decision_api/`.
- Don't run a second real Kaggle push to satisfy the LB-recorded test
  (M10-T004's row is the only LB row in M10).

## Acceptance criteria

- `tests/test_m10_smoke.py` exists, 4 tests, all PASS when
  `SUPABASE_DB_URL` is set and M10-T004 has produced a row.
- All 4 tests SKIP cleanly when `SUPABASE_DB_URL` is unset.
- Full `pytest tests/ services/decision_api/tests` matches the
  M10-T005 baseline + 4 new tests (no other regressions).
- `ruff check .` + `ruff format --check .` clean.

## Permissions

- `git commit` and `git push` deferred to milestone closeout.
- No real Kaggle calls.
- DB reads require `dangerouslyDisableSandbox=true` for the live-db
  job.

## Closeout format

```
M10-T006 closeout
  baseline_metric=<0.xxxx>     threshold ≥ <floor>          PASS | FAIL
  alt_metric=<0.xxxx>          ≥ baseline OR documented      PASS | FAIL
  submissions.public_score     <0.xxxx>                       PASS | FAIL
  kernel_push event recorded   YES | NO
  Acceptance: PASS | FAIL — assertion module landed at tests/test_m10_smoke.py (4 DB-gated tests; SKIP cleanly without SUPABASE_DB_URL, PASS against live local supabase-db)
  Files changed (staged, not committed): tests/test_m10_smoke.py (new, ~160 lines)
  Next: M10-T007 ready to start
```

## Related issues

- #12 — M10 proposal
- #17 — migration 0004 optional `submissions` columns. If still open
  at T006 time, query `submissions.public_score` (the column from
  `0001_init.sql`); after #17 closes, switch to `public_lb_score`.

## Stop condition

Stop after 60 turns. If any assertion FAILs against the recorded
M10-T002/004/005 evidence, HALT — failures here are the M9 rollback
"CV scores diverge in a way that suggests a leakage bug" condition,
and the fix is a re-run of the relevant prior Loop Prompt, not a
silent threshold lowering.
