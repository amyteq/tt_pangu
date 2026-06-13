-- 0011_m14_goal_loop.sql
-- M14: goal-driven Kaggle loop — goals table, competitions rules/limit
-- columns, submissions.goal_id FK, and experiment_runs.analysis_jsonb.
--
-- Forward-only. Idempotent. Additive. Every CREATE TABLE / ADD COLUMN /
-- CREATE INDEX is guarded with IF NOT EXISTS so the migration is safe to
-- re-apply (verified by applying twice in a row). The schema is the
-- contract between ADR-0020 / docs/architecture/goal-driven-kaggle-loop.md
-- and the M14 DB helpers + CLI surfaces (T001+).
--
-- Decision provenance (ADR-0020):
--   §2: goals table + FK from submissions; one active goal per competition.
--   §3: experiment_runs gains a NEW nullable analysis_jsonb column — NOT a
--       text→jsonb cast of the existing `analysis text` (0004:61), so M10's
--       free-text analysis rows are left untouched and the change is
--       trivially reversible (DROP COLUMN).
--   §7: competitions courtesy-limit + rules-ingestion columns (#8 / #7).
--       max_daily_submissions already exists (0001_init.sql:35); not re-added.

-- ---------------------------------------------------------------------------
-- Part A: goals — one declared target per competition (one active at a time).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS goals (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id    uuid NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  target_lb_score   numeric(10,6),
  target_lb_rank    int,
  target_rank_kind  text CHECK (target_rank_kind IN ('percentile', 'absolute')),
  deadline          timestamptz,
  exit_strategy     text NOT NULL CHECK (exit_strategy IN (
    'first_reached',
    'all_required',
    'score_only',
    'rank_only'
  )),
  max_total_pushes  int NOT NULL DEFAULT 20,
  stuck_threshold   int NOT NULL DEFAULT 3,
  status            text NOT NULL DEFAULT 'active' CHECK (status IN (
    'active',
    'reached',
    'closed',
    'abandoned'
  )),
  created_at        timestamptz NOT NULL DEFAULT now(),
  closed_at         timestamptz,
  closed_reason     text
);

-- One active goal per competition (ADR-0020 §2). A partial unique index
-- lets closed/reached/abandoned history accumulate while blocking a second
-- concurrent 'active' goal.
CREATE UNIQUE INDEX IF NOT EXISTS uq_goals_active_per_competition
  ON goals(competition_id) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_goals_competition
  ON goals(competition_id);

ALTER TABLE goals ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Part B: competitions — courtesy limits + rules / submission-format columns.
-- ADD COLUMN IF NOT EXISTS only; no existing column is altered or dropped.
-- max_daily_submissions already exists from 0001_init.sql (ensured below as
-- a no-op guard so a partially-migrated DB still gets it).
-- ---------------------------------------------------------------------------
ALTER TABLE competitions
  ADD COLUMN IF NOT EXISTS max_daily_submissions int,
  ADD COLUMN IF NOT EXISTS max_concurrent_pushes int,
  ADD COLUMN IF NOT EXISTS rules_summary_url     text,
  ADD COLUMN IF NOT EXISTS last_rules_fetch_at   timestamptz,
  ADD COLUMN IF NOT EXISTS submission_format     jsonb,
  ADD COLUMN IF NOT EXISTS accelerators_allowed  text[],
  ADD COLUMN IF NOT EXISTS internet_allowed      boolean,
  ADD COLUMN IF NOT EXISTS deadline_at           timestamptz;

-- ---------------------------------------------------------------------------
-- Part C: submissions.goal_id — attribute a push to the goal it served.
-- Nullable + ON DELETE SET NULL: M10's pre-goal submissions keep working,
-- and dropping a goal does not cascade-delete its submissions.
-- ---------------------------------------------------------------------------
ALTER TABLE submissions
  ADD COLUMN IF NOT EXISTS goal_id uuid REFERENCES goals(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_submissions_goal
  ON submissions(goal_id) WHERE goal_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Part D: experiment_runs.analysis_jsonb — loop metadata (ADR-0020 §3).
-- NEW nullable column alongside the existing `analysis text`; no cast.
-- Documented keys (no per-key schema): exploration_batch_id, parent_run_id,
-- queue_time_seconds, running_time_seconds, escalation_id.
-- ---------------------------------------------------------------------------
ALTER TABLE experiment_runs
  ADD COLUMN IF NOT EXISTS analysis_jsonb jsonb;

-- GIN index so the stuck-detector / explore-rank queries can filter by
-- analysis_jsonb keys (e.g. exploration_batch_id) without a full scan.
CREATE INDEX IF NOT EXISTS idx_experiment_runs_analysis_jsonb
  ON experiment_runs USING gin (analysis_jsonb)
  WHERE analysis_jsonb IS NOT NULL;
