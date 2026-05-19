-- 0004_m4_competition_repo.sql
-- M4: per-competition repo, experiment branches, runs, and submissions.
--
-- Forward-only. Idempotent. Additive — extends the M1/M2 tables in 0001 so
-- both the M2 (project_id+name) and M4 (competition_id+hypothesis) shapes
-- coexist. NOT NULL constraints are deferred for nullable additive columns
-- because existing rows would otherwise block ALTER.
--
-- No destructive drops.

-- ---------------------------------------------------------------------------
-- Part A: extend competitions with repo metadata + policy.
-- ---------------------------------------------------------------------------
ALTER TABLE competitions
  ADD COLUMN IF NOT EXISTS repo_url           text,
  ADD COLUMN IF NOT EXISTS default_branch     text NOT NULL DEFAULT 'main',
  ADD COLUMN IF NOT EXISTS local_clone_path   text,
  ADD COLUMN IF NOT EXISTS competition_policy jsonb NOT NULL DEFAULT '{}';

-- ---------------------------------------------------------------------------
-- Part B: experiments (M4 columns layered on the M1/M2 table).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id  uuid REFERENCES competitions(id) ON DELETE CASCADE,
  job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  hypothesis      text,
  branch          text,
  config          jsonb NOT NULL DEFAULT '{}',
  status          text NOT NULL DEFAULT 'active',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE experiments
  ADD COLUMN IF NOT EXISTS competition_id uuid REFERENCES competitions(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS job_id         uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS branch         text,
  ADD COLUMN IF NOT EXISTS updated_at     timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_experiments_competition
  ON experiments(competition_id) WHERE competition_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_experiments_job
  ON experiments(job_id) WHERE job_id IS NOT NULL;

ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Part C: experiment_runs (M4 columns layered on the M1/M2 table).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS experiment_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id   uuid NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  run_dir         text,
  command         text,
  status          text NOT NULL DEFAULT 'running',
  metrics         jsonb NOT NULL DEFAULT '{}',
  artifact_paths  jsonb NOT NULL DEFAULT '[]',
  analysis        text,
  started_at      timestamptz,
  finished_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE experiment_runs
  ADD COLUMN IF NOT EXISTS job_id         uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS run_dir        text,
  ADD COLUMN IF NOT EXISTS artifact_paths jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS finished_at    timestamptz;

CREATE INDEX IF NOT EXISTS idx_experiment_runs_experiment
  ON experiment_runs(experiment_id);

CREATE INDEX IF NOT EXISTS idx_experiment_runs_job
  ON experiment_runs(job_id) WHERE job_id IS NOT NULL;

ALTER TABLE experiment_runs ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Part D: submissions (M4 columns layered on the M1/M2 table).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS submissions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id  uuid REFERENCES competitions(id) ON DELETE CASCADE,
  run_id          uuid,  -- FK added below conditionally on M4 column existing
  job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  file_path       text,
  public_lb_score numeric(10,6),
  cv_score        numeric(10,6),
  note            text,
  status          text NOT NULL DEFAULT 'prepared',
  submitted_at    timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE submissions
  ADD COLUMN IF NOT EXISTS run_id          uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS file_path       text,
  ADD COLUMN IF NOT EXISTS public_lb_score numeric(10,6),
  ADD COLUMN IF NOT EXISTS cv_score        numeric(10,6),
  ADD COLUMN IF NOT EXISTS note            text;

CREATE INDEX IF NOT EXISTS idx_submissions_competition
  ON submissions(competition_id) WHERE competition_id IS NOT NULL;

ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
