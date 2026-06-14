# M6-T000: Migration 0006 — agent_reviews + agent_telemetry_spans

## Milestone
M6: multi-agent review, OTEL telemetry, local-model layer.

## Goal
Add the two M6-specific tables and the `otel_span_id` column on `agent_jobs`
so reviewer verdicts and telemetry spans can be persisted in Supabase
alongside the M3 job lifecycle and M5 research items.

## Read first
1. `supabase/migrations/0005_m5_research_citations.sql` — additive ALTER style.
2. `supabase/migrations/0003_m3_worker.sql` — `agent_jobs` shape + `agent_job_events`.
3. `docs/adr/0007-otel-telemetry-strategy.md` — span hierarchy.
4. `docs/milestones/README.md` (M6 section).

## Schema additions

### Part A — `agent_reviews`
```sql
CREATE TABLE IF NOT EXISTS agent_reviews (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id          uuid NOT NULL REFERENCES agent_jobs(id) ON DELETE CASCADE,
  run_id          uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
  reviewer_model  text NOT NULL,                 -- claude-opus-4-7, rtx4090, etc.
  reviewer_kind   text NOT NULL DEFAULT 'sync',  -- 'sync' | 'async_postmortem'
  target_op       text,                          -- kaggle_submit, supabase_migrate, ...
  verdict         text NOT NULL,                 -- approve | reject | abstain
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
```

### Part B — `agent_telemetry_spans`
```sql
CREATE TABLE IF NOT EXISTS agent_telemetry_spans (
  id            bigserial PRIMARY KEY,
  trace_id      text NOT NULL,
  span_id       text NOT NULL,
  parent_span_id text,
  job_id        uuid REFERENCES agent_jobs(id) ON DELETE CASCADE,
  kind          text NOT NULL,         -- job | turn | tool | llm | review | local_probe
  name          text NOT NULL,
  started_at    timestamptz NOT NULL,
  ended_at      timestamptz,
  duration_ms   bigint,
  attributes    jsonb NOT NULL DEFAULT '{}',
  status        text NOT NULL DEFAULT 'ok',  -- ok | error
  error         text
);
CREATE INDEX IF NOT EXISTS idx_telemetry_trace ON agent_telemetry_spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_job   ON agent_telemetry_spans(job_id) WHERE job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_telemetry_kind  ON agent_telemetry_spans(kind);
ALTER TABLE agent_telemetry_spans ENABLE ROW LEVEL SECURITY;
```

### Part C — extend `agent_jobs`
```sql
ALTER TABLE agent_jobs
  ADD COLUMN IF NOT EXISTS otel_trace_id text,
  ADD COLUMN IF NOT EXISTS otel_root_span_id text;
```

## Acceptance criteria
- `psql -v ON_ERROR_STOP=1 -f supabase/migrations/0006_*.sql` exits 0 on
  first apply and re-apply.
- `\d agent_reviews` and `\d agent_telemetry_spans` show all listed columns.
- `\d agent_jobs` shows `otel_trace_id` + `otel_root_span_id`.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 20 turns. If existing rows block a NOT NULL constraint, make the
column nullable and note the choice in the migration header.
