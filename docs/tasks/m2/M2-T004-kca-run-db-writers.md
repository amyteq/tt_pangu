# M2-T004: kca run ↔ DB writers (DB-first)

## Milestone
M2: Supabase / control-plane foundation.

## Goal
Make the DB the source of truth for `kca run init`, `kca run record-metric`,
and `kca run list`. JSON files in `runs/<comp>/<run_id>/` become a cache
derived from the DB write, written only AFTER the DB commit succeeds.

This is the meaningful behavioral change of M2 — kca becomes online-required.

## Read first
1. `tools/kca/run.py` (current behavior)
2. `tools/kca/db.py` (from T003)
3. `tests/test_kca_smoke.py` (will need updating)

## Required behavioral changes

### `kca run init`
Order of operations:
1. `ensure_default_project()` (or accept `--project <name>`).
2. `ensure_competition(slug)`.
3. Compute external_run_id = `--run-id` arg or UTC `YYYYMMDD_HHMMSS`.
4. Compute `run_dir = runs/<slug>/<external_run_id>/`.
5. `create_experiment(project_id, name=external_run_id, hypothesis, tags, config={})`.
6. `create_experiment_run(experiment_id, external_run_id, run_dir)`.
7. **If all DB writes succeeded**, mkdir `run_dir/{logs,artifacts}` and write `meta.json`, `config.json`, `metrics.json` (cache).
8. Emit JSON envelope including both `experiment_run_id` (uuid) and `run_dir`.

If any DB write fails: no filesystem state is created; emit `ok: false` with the underlying error; exit non-zero.

### `kca run record-metric`
Order of operations:
1. Resolve experiment_run by `--run-dir` (look up `external_run_id` from path) or `--experiment-run-id <uuid>`.
2. `record_metric(experiment_run_id, key, value)`.
3. After DB commit, rewrite `<run_dir>/metrics.json` from DB state.

### `kca run list`
Reads from DB only. The filesystem layout is no longer canonical.

## Design constraints
- DB is the gating commit. Filesystem writes follow.
- Cache files (`meta.json`, `metrics.json`) are best-effort — if the cache write fails after DB commit, log a warning to stderr but exit 0 with `cache_warning` in the envelope.
- Keep the existing JSON envelope shape backward-compatible; add new fields, don't rename.

## Non-goals
- Do not migrate existing `runs/` state to the DB. Users start fresh; old run dirs are legacy.
- Do not change `kca nb*` or `kca kaggle*` behavior in this task.

## Acceptance criteria
- After `kca run init --competition titanic --hypothesis "h"`, a row exists in `experiments` and `experiment_runs` referencing it; `runs/titanic/<ts>/meta.json` exists.
- If the DB is unreachable, `kca run init` exits non-zero and creates no filesystem state.
- `kca run record-metric` writes one `experiment_run_metrics` row, updates `experiment_runs.metrics` jsonb, and refreshes `runs/.../metrics.json`.
- `kca run list --competition titanic` returns the new run, sourced from the DB join.
- All existing smoke tests in `tests/test_kca_smoke.py` still pass (or are updated to assert both DB and FS state).

## Suggested checks
```bash
make supabase-up
SUPABASE_DB_URL="postgres://postgres:postgres@localhost:54322/postgres" \
  python tools/kca/kca.py run init --competition titanic --hypothesis "baseline" --json
psql "$SUPABASE_DB_URL" -c "select id, external_run_id, run_dir from experiment_runs;"
```

## Stop condition
Stop after 60 turns if the DB-first ordering causes test flakiness or
unrecoverable transaction failures. Record the failure mode and propose
fallback to dual-write with reconciliation.
