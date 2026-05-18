# M2-T003: Python DB access layer (psycopg)

## Milestone
M2: Supabase / control-plane foundation.

## Goal
Provide a small, well-tested Python module that the kca CLI uses to read/write
the M2 schema. Sync-only psycopg3; no ORM; no Supabase REST. Keep the contract
narrow: just the operations the kca commands need.

## Read first
1. `supabase/migrations/0001_init.sql` and `0002_kca_run_alignment.sql`
2. `tools/kca/run.py` (current operations to mirror)
3. `tools/kca/_util.py` (envelope conventions)
4. ADR-002 (control plane), ADR-003 (approval gates)

## Required deliverables
- `tools/kca/db.py` — public functions used by other kca modules:
  - `get_conn()` — returns a psycopg3 connection, configured from env.
  - `ensure_competition(slug, platform='kaggle')` → `competition_id`.
  - `ensure_default_project()` → `project_id` (the bootstrap row from T001).
  - `create_experiment(project_id, name, hypothesis, tags, config)` → `experiment_id`.
  - `create_experiment_run(experiment_id, external_run_id, run_dir, command=None)` → `experiment_run_id`.
  - `record_metric(experiment_run_id, key, value)` → inserts into `experiment_run_metrics` AND updates `experiment_runs.metrics` jsonb.
  - `list_runs(competition_slug=None)` → joined view of runs.
  - `insert_approval_request(session_id, decision_type, prompt, options)` → for M2-T005.
- Env var contract:
  - `KCA_DB_TARGET` — `local` (default) or `remote`. `remote` requires `KCA_ALLOW_REMOTE=1` (mirrors kaggle Layer A).
  - `SUPABASE_DB_URL` — psycopg connection string (preferred).
  - Fall back to discrete `SUPABASE_DB_HOST` / `PORT` / `USER` / `PASSWORD` / `DB` if URL not set.
- Side-effect classification:
  - All `db.py` operations are `LOCAL_WRITE` when `KCA_DB_TARGET=local`.
  - They become `REMOTE_WRITE` when `KCA_DB_TARGET=remote`; gated identically to `kaggle submit`.
- Errors surface as exceptions; callers wrap them into the kca JSON envelope.

## Design constraints
- psycopg3 only (`psycopg[binary]` is fine for local dev; pinning to base for prod).
- No async. No connection pooling in M2 — open/close per operation (cheap on local).
- No ORM. Use parameterized SQL strings; never f-string interpolate user input.
- Functions take simple Python types; return dicts or domain primitives.
- Module must be importable without a live DB (so help / --dry-run still works); connection happens lazily.

## Non-goals
- No async (M3+).
- No connection pooling (M3+).
- No migrations runner (Supabase CLI owns this).
- No Supabase Auth/JWT in M2 — service role connection string locally.

## Acceptance criteria
- `python -c "from tools.kca import db; print(db.__all__)"` lists the public API.
- With a live local Supabase, a script that calls `ensure_default_project` → `ensure_competition` → `create_experiment` → `create_experiment_run` → `record_metric` succeeds and inserts the expected rows.
- Without a live DB, `import db` does not raise; only calls to `get_conn()` would fail.
- `KCA_DB_TARGET=remote` without `KCA_ALLOW_REMOTE=1` raises a clear `RemoteOperationBlocked` exception.

## Suggested checks
```bash
python -c "from tools.kca import db; print(db.__all__)"
# With local Supabase up:
KCA_DB_TARGET=local SUPABASE_DB_URL="postgres://postgres:postgres@localhost:54322/postgres" \
  python -c "from tools.kca import db; print(db.ensure_default_project())"
```

## Stop condition
Stop after 50 turns if psycopg3 install or local DB connection is wedged —
record the failure and propose either a docker-based Postgres or pinning
older psycopg2.
