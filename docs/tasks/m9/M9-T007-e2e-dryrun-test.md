# M9-T007: tests/test_m9_e2e.py — dry-run path

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Add a credentials-free, no-real-Kaggle dry-run smoke test that exercises
the full M9 worker path: research → baseline → CV → submission.csv →
reviewer gate → decision approve. This is the CI-friendly version of M9
that runs on every PR.

This task assumes the M9 worker path is stable (M9-T002, M9-T003 PASS).

## Read first

1. `tests/test_m8_smoke.py`, `tests/test_m8_worker_wiring.py` (pattern)
2. `src/worker/worker.py` — `dry_run=True` path
3. `tools/kca/kg.py::cmd_submit` (verify it refuses without
   `KAGGLE_USERNAME`/`KAGGLE_KEY`)
4. `tests/conftest.py` (existing fixtures)

## Scope

1. Add `tests/test_m9_e2e.py` containing one or more tests that:
   - run the worker in `dry_run=True` mode against a fixture data slice
     (a few rows of train/test stored under `tests/fixtures/spaceship-titanic/`);
   - produce a fake `submission.csv`;
   - drive the reviewer gate (still writes audit rows in dry-run, per
     M8 wiring);
   - approve via the decision_api test client;
   - verify `kca kaggle submit` refuses (or `cmd_submit` returns an
     error code) when `KAGGLE_USERNAME` is unset — i.e. the credentials
     gate fires.
2. Make sure the test does NOT require network access to `kaggle.com`.
3. Make sure the test does NOT require `SUPABASE_DB_URL` — use the
   in-memory / JSONL audit path (M3+ tests already do this).
4. Ensure CI's `no-db` and `live-db` jobs both pick the test up. Update
   the `live-db` job only if the test legitimately requires DB.

## Non-goals

- No real Kaggle call.
- No real Anthropic API.
- No new dependencies (test should use what's already in `pyproject.toml`).
- No test that depends on a live `services/decision_api/` process —
  use FastAPI's `TestClient`.

## Acceptance criteria

- `python -m pytest tests/test_m9_e2e.py -v` — 0 failures, no network,
  no credentials.
- The test runs and passes in the `no-db` CI job (verify locally without
  `SUPABASE_DB_URL`).
- The test exercises the credentials-gate refusal path.
- All baseline validation still passes (pytest, ruff, pnpm).

## Permissions

- No network out. No DB. No real Kaggle.
- `git commit` / `git push` deferred to milestone closeout.

## Closeout format

```
M9-T007 closeout
  New file: tests/test_m9_e2e.py
  Fixtures: tests/fixtures/spaceship-titanic/{train,test,sample_submission}.csv (small slices)
  pytest result: <n> passed, 0 failed, network=NO, db=NO
  Credentials-gate refusal asserted: YES
  Acceptance: PASS | FAIL — link to issue
  Next: M9-T008 ready to start
```

## Stop condition

Stop after 60 turns. If the test ends up needing real network, halt and
reconsider the fixture — do NOT relax the no-network rule.
