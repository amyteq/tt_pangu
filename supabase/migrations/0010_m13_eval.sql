-- 0010_m13_eval.sql
-- M13: regression-suite framework — eval_suites + eval_runs + eval_results.
--
-- Renumbered from 0008 → 0010 during the M11+M12 merge integration:
-- M11 (CTF/lab workflow) took migration 0008, M12 (Devpost/hackathon)
-- took 0009. M13's eval tables move to 0010. The CREATE TABLE
-- statements remain unchanged; the file rename is purely organizational.
--
-- Forward-only. Idempotent. Additive. All CREATE TABLE / CREATE INDEX
-- statements are guarded with IF NOT EXISTS so the migration is safe to
-- re-apply. The schema is the contract between ADR-0019 / the architecture
-- doc and the kca eval CLI scaffold (T001) + per-suite drivers (T002+).
--
-- Naming follows the M13-T001 task-spec column list verbatim (task spec is
-- authoritative when it diverges from the architecture doc's preliminary
-- column sketch).

-- ---------------------------------------------------------------------------
-- Part A: eval_suites — slow-changing registry of registered suites.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eval_suites (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL UNIQUE,
  description text,
  version     text NOT NULL,
  category    text NOT NULL CHECK (category IN (
    'tool_smoke',
    'kaggle_replay',
    'kernel_dryrun',
    'reasoning',
    'model_route_compare'
  )),
  metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eval_suites_category
  ON eval_suites(category);

ALTER TABLE eval_suites ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Part B: eval_runs — one row per `kca eval run` invocation.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eval_runs (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at         timestamptz NOT NULL DEFAULT now(),
  finished_at        timestamptz,
  route              text NOT NULL,
  dry_run            boolean NOT NULL DEFAULT true,
  total_cases        integer NOT NULL DEFAULT 0,
  total_pass         integer,
  total_fail         integer,
  total_skip         integer,
  aborted_on_budget  boolean NOT NULL DEFAULT false,
  budget_usd         numeric(10,4),
  cost_usd           numeric(10,4),
  metadata           jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_started_at
  ON eval_runs(started_at DESC);

ALTER TABLE eval_runs ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Part C: eval_results — one row per (case × route) under a given run.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eval_results (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id      uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  suite_id    uuid NOT NULL REFERENCES eval_suites(id),
  case_name   text NOT NULL,
  route       text NOT NULL,
  status      text NOT NULL CHECK (status IN ('pass', 'fail', 'skip', 'error')),
  metrics     jsonb NOT NULL DEFAULT '{}'::jsonb,
  latency_ms  integer,
  cost_usd    numeric(10,4),
  error_text  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eval_results_run_id
  ON eval_results(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_suite_route
  ON eval_results(suite_id, route);

ALTER TABLE eval_results ENABLE ROW LEVEL SECURITY;
