# M4-T001: Migration 0004 — competition repo + experiment/run/submission tables

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Extend the Postgres schema with:
1. Competition repo columns (ADR-0009): `repo_url`, `default_branch`, `local_clone_path`.
2. `experiments` table — hypothesis + config being tested.
3. `experiment_runs` table — one execution of an experiment.
4. `submissions` table — prepared/submitted files.

## Read first
1. `supabase/migrations/0001_init.sql` — `competitions` table definition
2. `supabase/migrations/0003_m3_worker.sql` — migration style (idempotent, IF NOT EXISTS)
3. `docs/adr/0009-competition-repo-strategy.md` — DB schema section
4. `docs/adr/0005-job-taxonomy.md` — definitions of experiment, run, submission

## Migration: `supabase/migrations/0004_m4_competition_repo.sql`

Forward-only. Idempotent. No destructive drops.

### 1. Extend `competitions`

```sql
ALTER TABLE competitions
  ADD COLUMN IF NOT EXISTS repo_url         text,
  ADD COLUMN IF NOT EXISTS default_branch   text NOT NULL DEFAULT 'main',
  ADD COLUMN IF NOT EXISTS local_clone_path text,
  ADD COLUMN IF NOT EXISTS competition_policy jsonb NOT NULL DEFAULT '{}';
```

`competition_policy` jsonb shape:
```json
{
  "approval_gates": {
    "kaggle_submit": false,
    "kernel_push": false
  },
  "max_daily_submissions": 10
}
```

### 2. Create `experiments`

```sql
CREATE TABLE IF NOT EXISTS experiments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id  uuid NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  hypothesis      text NOT NULL,
  branch          text,          -- exp/<slug> in competition repo
  config          jsonb NOT NULL DEFAULT '{}',
  -- config: model_spec, cv_strategy, hyperparams, data_version
  status          text NOT NULL DEFAULT 'active',
  -- active | archived | submitted
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_experiments_competition
  ON experiments(competition_id);
CREATE INDEX IF NOT EXISTS idx_experiments_job
  ON experiments(job_id) WHERE job_id IS NOT NULL;

ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;
```

### 3. Create `experiment_runs`

```sql
CREATE TABLE IF NOT EXISTS experiment_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id   uuid NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  run_dir         text,          -- runs/<comp>/<run_id>/ on disk
  command         text,
  status          text NOT NULL DEFAULT 'running',
  -- running | succeeded | failed
  metrics         jsonb NOT NULL DEFAULT '{}',
  -- {"cv_score": 0.82, "val_loss": 0.12, "runtime_s": 45}
  artifact_paths  jsonb NOT NULL DEFAULT '[]',
  analysis        text,
  started_at      timestamptz,
  finished_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_runs_experiment
  ON experiment_runs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_runs_job
  ON experiment_runs(job_id) WHERE job_id IS NOT NULL;

ALTER TABLE experiment_runs ENABLE ROW LEVEL SECURITY;
```

### 4. Create `submissions`

```sql
CREATE TABLE IF NOT EXISTS submissions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id  uuid NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  run_id          uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
  job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  file_path       text NOT NULL,
  public_lb_score numeric(10,6),
  cv_score        numeric(10,6),
  note            text,
  status          text NOT NULL DEFAULT 'prepared',
  -- prepared | submitted | scored | selected_final
  submitted_at    timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_submissions_competition
  ON submissions(competition_id);

ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
```

## Acceptance criteria
- Migration applies cleanly on top of 0001–0003: `psql $SUPABASE_DB_URL < supabase/migrations/0004_m4_competition_repo.sql`
- Idempotent: applying twice produces no error.
- `psql $SUPABASE_DB_URL -c "\d competitions"` shows `repo_url`, `default_branch`, `local_clone_path`.
- `psql $SUPABASE_DB_URL -c "\dt"` lists `experiments`, `experiment_runs`, `submissions`.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 30 turns. If a Postgres type error occurs (enum vs text mismatch),
document the exact error and propose the minimal fix — do not attempt a full schema
rewrite.
