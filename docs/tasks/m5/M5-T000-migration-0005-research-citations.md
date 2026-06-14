# M5-T000: Migration 0005 — research item extensions

## Milestone
M5: research and browser workflow.

## Goal
Extend the existing `research_items` table (from 0001) with the fields M5
needs to record cited, trust-labelled web research and link it to runs and
experiments. Add a tightly-scoped `research_citations` join table so a single
research item can be cited by multiple runs/experiments without duplicating
text.

## Read first
1. `supabase/migrations/0001_init.sql` — current `research_items` columns
2. `supabase/migrations/0004_m4_competition_repo.sql` — additive ALTER style
3. `docs/adr/0009-competition-repo-strategy.md` — competition_id linkage
4. `docs/milestones/README.md` (M5 section)

## Schema additions

### Part A — extend `research_items`
```sql
ALTER TABLE research_items
  ADD COLUMN IF NOT EXISTS competition_id    uuid REFERENCES competitions(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS source_kind       text,           -- 'page' | 'pdf' | 'discussion' | 'kernel' | 'paper'
  ADD COLUMN IF NOT EXISTS html_artifact_id  uuid REFERENCES artifacts(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS text_artifact_id  uuid REFERENCES artifacts(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS fetcher           text,           -- 'http' | 'playwright' | 'mcp'
  ADD COLUMN IF NOT EXISTS content_hash      text,
  ADD COLUMN IF NOT EXISTS http_status       int,
  ADD COLUMN IF NOT EXISTS source_policy     jsonb NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_research_items_competition
  ON research_items(competition_id) WHERE competition_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_research_items_hash
  ON research_items(content_hash) WHERE content_hash IS NOT NULL;
```

### Part B — `research_citations` join table
```sql
CREATE TABLE IF NOT EXISTS research_citations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  research_item_id uuid NOT NULL REFERENCES research_items(id) ON DELETE CASCADE,
  run_id          uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
  experiment_id   uuid REFERENCES experiments(id) ON DELETE SET NULL,
  job_id          uuid REFERENCES agent_jobs(id) ON DELETE SET NULL,
  quote           text,
  page_anchor     text,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_research_citations_item
  ON research_citations(research_item_id);
CREATE INDEX IF NOT EXISTS idx_research_citations_run
  ON research_citations(run_id) WHERE run_id IS NOT NULL;
ALTER TABLE research_citations ENABLE ROW LEVEL SECURITY;
```

## Acceptance criteria
- `psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 < supabase/migrations/0005_m5_research_citations.sql`
  exits 0 on first apply.
- Re-apply produces only `NOTICE: ... already exists` lines and exits 0.
- `psql "$SUPABASE_DB_URL" -c "\d research_items"` shows the 8 new columns.
- `psql "$SUPABASE_DB_URL" -c "\dt research_citations"` shows the new table.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 20 turns. If `research_items` cannot be ALTERed (existing rows
violate a new NOT NULL), make the column nullable and document the choice in
the migration header.
