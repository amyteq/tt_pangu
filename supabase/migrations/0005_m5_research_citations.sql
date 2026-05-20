-- 0005_m5_research_citations.sql
-- M5: extend research_items with M5 fields and add research_citations.
--
-- Forward-only. Idempotent. Additive. All new columns are nullable (or have
-- defaults) so existing rows do not block the ALTER.

-- ---------------------------------------------------------------------------
-- Part A: extend research_items.
-- ---------------------------------------------------------------------------
ALTER TABLE research_items
  ADD COLUMN IF NOT EXISTS competition_id    uuid REFERENCES competitions(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS source_kind       text,
  ADD COLUMN IF NOT EXISTS html_artifact_id  uuid REFERENCES artifacts(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS text_artifact_id  uuid REFERENCES artifacts(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS fetcher           text,
  ADD COLUMN IF NOT EXISTS content_hash      text,
  ADD COLUMN IF NOT EXISTS http_status       int,
  ADD COLUMN IF NOT EXISTS source_policy     jsonb NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_research_items_competition
  ON research_items(competition_id) WHERE competition_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_research_items_hash
  ON research_items(content_hash) WHERE content_hash IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Part B: research_citations join table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS research_citations (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  research_item_id uuid NOT NULL REFERENCES research_items(id) ON DELETE CASCADE,
  run_id           uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
  experiment_id    uuid REFERENCES experiments(id) ON DELETE SET NULL,
  job_id           uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  quote            text,
  page_anchor      text,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_citations_item
  ON research_citations(research_item_id);

CREATE INDEX IF NOT EXISTS idx_research_citations_run
  ON research_citations(run_id) WHERE run_id IS NOT NULL;

ALTER TABLE research_citations ENABLE ROW LEVEL SECURITY;
