-- 0003_m3_worker.sql
-- Extend schema to support M3 worker lifecycle: per-job policy, workspace
-- tracking, per-turn event logging, and decision-to-job linkage.
--
-- Forward-only. Idempotent. No destructive drops.

-- ---------------------------------------------------------------------------
-- 1. Extend job_status enum with 'paused' value.
-- ---------------------------------------------------------------------------
ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'paused' AFTER 'running';

-- ---------------------------------------------------------------------------
-- 2. Add worker columns to agent_jobs.
-- ---------------------------------------------------------------------------
-- Policy jsonb shape:
-- {
--   "max_turns": 30,
--   "max_cost_usd": 5.0,
--   "max_runtime_s": 3600,
--   "allowed_tool_patterns": ["kca *", "pytest *"],
--   "max_side_effect": "LOCAL_WRITE"
-- }
ALTER TABLE agent_jobs
  ADD COLUMN IF NOT EXISTS workspace_path text,
  ADD COLUMN IF NOT EXISTS prompt         text,
  ADD COLUMN IF NOT EXISTS model          text NOT NULL DEFAULT 'claude-sonnet-4-6',
  ADD COLUMN IF NOT EXISTS turns_used     int  NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cost_usd       numeric(10,4) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS policy         jsonb NOT NULL DEFAULT '{}';

-- ---------------------------------------------------------------------------
-- 3. Create agent_job_events — append-only turn/tool event log.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_job_events (
  id            bigserial PRIMARY KEY,
  job_id        uuid NOT NULL REFERENCES agent_jobs(id) ON DELETE CASCADE,
  event_type    text NOT NULL,
  -- values: turn_start | tool_call | tool_result | approval_pause
  --         approval_resume | budget_stop | done | error
  turn_number   int,
  input_tokens  int,
  output_tokens int,
  cost_usd      numeric(10,4),
  event_data    jsonb NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_turn
  ON agent_job_events(job_id, turn_number);

CREATE INDEX IF NOT EXISTS idx_job_events_type
  ON agent_job_events(event_type);

ALTER TABLE agent_job_events ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 4. Link human_decisions back to agent_jobs.
-- ---------------------------------------------------------------------------
ALTER TABLE human_decisions
  ADD COLUMN IF NOT EXISTS job_id uuid REFERENCES agent_jobs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_human_decisions_job
  ON human_decisions(job_id) WHERE job_id IS NOT NULL;
