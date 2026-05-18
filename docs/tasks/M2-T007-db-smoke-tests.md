# M2-T007: DB smoke tests

## Milestone
M2: Supabase / control-plane foundation.

## Goal
Add a pytest smoke test suite that exercises the kca↔DB path end-to-end
against a live local Supabase. Skippable via env var so CI without
Supabase doesn't fail.

## Read first
1. `tests/test_kca_smoke.py` (style reference)
2. `tools/kca/db.py` (T003)
3. `tools/kca/run.py` (after T004)

## Required deliverable
- `tests/test_kca_db_smoke.py` with pytest cases:
  - `test_run_init_writes_db_and_fs` — `kca run init` inserts experiment + experiment_run, and writes meta.json.
  - `test_record_metric_writes_event_and_jsonb` — `kca run record-metric` adds an `experiment_run_metrics` row AND updates `experiment_runs.metrics` jsonb.
  - `test_run_list_sources_from_db` — `kca run list` returns the run from the DB join.
  - `test_db_unreachable_fails_cleanly` — point `SUPABASE_DB_URL` at a closed port; `kca run init` exits non-zero with `ok: false` and creates no filesystem state.
  - `test_kaggle_submit_blocks_and_records_approval` — `kca kaggle submit` blocked path inserts a `pending` `human_decisions` row.
- Module-level `pytest.importorskip("psycopg")` and `pytest.skipif(not os.environ.get("KCA_DB_TARGET"))` guards.
- Each test uses a unique competition slug (e.g., `f"smoke_{uuid.uuid4().hex[:8]}"`) for isolation; clean up afterwards.

## Design constraints
- Tests must not write to the filesystem outside `tmp_path` for cache state (override `RUNS_ROOT` via env if needed).
- Tests must clean up DB rows they created.
- No network calls beyond localhost.

## Non-goals
- No CI integration in this task (separate follow-up to wire `supabase start` into GitHub Actions).
- No performance / load tests.

## Acceptance criteria
- `KCA_DB_TARGET=local SUPABASE_DB_URL=... python -m pytest tests/test_kca_db_smoke.py -v` → all pass against a fresh local Supabase.
- Without `KCA_DB_TARGET` set, the suite is skipped (exit 0, "5 skipped").
- Existing `tests/test_kca_smoke.py` still passes (unchanged contract).

## Suggested checks
```bash
make supabase-up
KCA_DB_TARGET=local SUPABASE_DB_URL="postgres://postgres:postgres@localhost:54322/postgres" \
  python -m pytest tests/test_kca_db_smoke.py -v
```

## Stop condition
Stop after 40 turns if any test reveals an inconsistency between DB and FS
state that T004's design can't reconcile. Record the inconsistency and
propose either a schema fix (T001 follow-up) or a behavior change in T004.
