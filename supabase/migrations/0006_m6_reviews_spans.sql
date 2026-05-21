-- 0006_m6_reviews_spans.sql
-- M6: agent_reviews + agent_telemetry_spans + agent_jobs.otel_* columns.
--
-- Forward-only. Idempotent. Additive. All new columns are nullable or have
-- defaults so existing rows do not block the ALTER. Safe to re-apply.

-- ---------------------------------------------------------------------------
-- Part A: agent_reviews
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_reviews (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id          uuid NOT NULL REFERENCES agent_jobs(id) ON DELETE CASCADE,
  run_id          uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
  reviewer_model  text NOT NULL,
  reviewer_kind   text NOT NULL DEFAULT 'sync',
  target_op       text,
  verdict         text NOT NULL,
  rationale       text,
  evidence        jsonb NOT NULL DEFAULT '{}',
  cost_usd        numeric(10,4) NOT NULL DEFAULT 0,
  decision_id     uuid REFERENCES human_decisions(id) ON DELETE SET NULL,
  otel_span_id    text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_reviews_job
  ON agent_reviews(job_id);
CREATE INDEX IF NOT EXISTS idx_agent_reviews_target_op
  ON agent_reviews(target_op);

ALTER TABLE agent_reviews ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Part B: agent_telemetry_spans
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_telemetry_spans (
  id             bigserial PRIMARY KEY,
  trace_id       text NOT NULL,
  span_id        text NOT NULL,
  parent_span_id text,
  job_id         uuid REFERENCES agent_jobs(id) ON DELETE CASCADE,
  kind           text NOT NULL,
  name           text NOT NULL,
  started_at     timestamptz NOT NULL,
  ended_at       timestamptz,
  duration_ms    bigint,
  attributes     jsonb NOT NULL DEFAULT '{}',
  status         text NOT NULL DEFAULT 'ok',
  error          text
);

CREATE INDEX IF NOT EXISTS idx_telemetry_trace
  ON agent_telemetry_spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_job
  ON agent_telemetry_spans(job_id) WHERE job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_telemetry_kind
  ON agent_telemetry_spans(kind);

ALTER TABLE agent_telemetry_spans ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Part C: extend agent_jobs with OTEL identifiers
-- ---------------------------------------------------------------------------
ALTER TABLE agent_jobs
  ADD COLUMN IF NOT EXISTS otel_trace_id     text,
  ADD COLUMN IF NOT EXISTS otel_root_span_id text;
