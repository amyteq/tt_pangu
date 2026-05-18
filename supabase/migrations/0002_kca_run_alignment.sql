-- 0002_kca_run_alignment.sql
-- Align the M0 Supabase schema with M1's kca run artifacts so the kca CLI
-- can write runs/metrics/projects to Postgres as the source of truth
-- (filesystem JSON files become a cache; see M2-T004).
--
-- Forward-only. Idempotent where reasonable. No destructive drops.

-- ---------------------------------------------------------------------------
-- 1) Bootstrap project row so local kca calls have something to attach to.
-- ---------------------------------------------------------------------------
-- The id is a fixed namespace UUID so the kca client can hard-code it.
insert into projects (id, name, kind, description)
values (
  '00000000-0000-0000-0000-000000000001',
  'local-default',
  'general',
  'Default project for local kca calls when no explicit project is configured.'
)
on conflict (id) do nothing;


-- ---------------------------------------------------------------------------
-- 2) experiment_runs: track M1's string run_id and filesystem cache path.
-- ---------------------------------------------------------------------------
alter table experiment_runs
  add column if not exists external_run_id text,
  add column if not exists run_dir text;

-- One external_run_id per experiment (M1's "20260517_101109" style timestamp).
-- Partial unique index so legacy rows with NULL external_run_id are unaffected.
create unique index if not exists uq_experiment_runs_external
  on experiment_runs(experiment_id, external_run_id)
  where external_run_id is not null;

-- Lookup index for "find this run by its filesystem path" (used by
-- `kca run record-metric --run-dir ...`).
create index if not exists idx_experiment_runs_run_dir
  on experiment_runs(run_dir)
  where run_dir is not null;


-- ---------------------------------------------------------------------------
-- 3) experiments: tags array, mirrored from meta.json `tags`.
-- ---------------------------------------------------------------------------
alter table experiments
  add column if not exists tags text[] not null default '{}';


-- ---------------------------------------------------------------------------
-- 4) experiment_run_metrics: append-only event log for metric values.
--
-- experiment_runs.metrics jsonb is kept as a denormalized snapshot
-- (last-value-wins) so callers can read the current state cheaply.
-- This table is the audit trail.
-- ---------------------------------------------------------------------------
create table if not exists experiment_run_metrics (
  id bigserial primary key,
  experiment_run_id uuid not null
    references experiment_runs(id) on delete cascade,
  key text not null,
  value numeric not null,
  recorded_at timestamptz not null default now(),
  metadata jsonb not null default '{}'
);

create index if not exists idx_run_metrics_run_recorded
  on experiment_run_metrics(experiment_run_id, recorded_at desc);

create index if not exists idx_run_metrics_key
  on experiment_run_metrics(key);

alter table experiment_run_metrics enable row level security;


-- ---------------------------------------------------------------------------
-- 5) competitions: speed up slug lookups (kca run init takes a slug).
-- ---------------------------------------------------------------------------
-- The existing unique constraint is on (platform, slug); a slug-only lookup
-- still hits that index but a plain (slug) index helps when platform is
-- inferred / filtered separately.
create index if not exists idx_competitions_slug
  on competitions(slug);


-- ---------------------------------------------------------------------------
-- 6) human_decisions: indexes to support the M2-T005 "pending approvals"
--    inbox query pattern.
-- ---------------------------------------------------------------------------
create index if not exists idx_human_decisions_status_created
  on human_decisions(status, created_at desc);

create index if not exists idx_human_decisions_type_status
  on human_decisions(decision_type, status);


-- ---------------------------------------------------------------------------
-- 7) Column comments — useful in Studio when humans browse the schema.
-- ---------------------------------------------------------------------------
comment on column experiment_runs.external_run_id is
  'kca run_id string (e.g. ''20260517_101109''). Stable handle from the filesystem cache.';
comment on column experiment_runs.run_dir is
  'Filesystem path under runs/<comp>/<run_id>/ where the cached JSON files live. Relative to repo root.';
comment on column experiments.tags is
  'Free-form tags from meta.json (e.g. ["baseline", "gpu"]).';
comment on table experiment_run_metrics is
  'Append-only metric event log. experiment_runs.metrics is the denormalized last-value snapshot.';
