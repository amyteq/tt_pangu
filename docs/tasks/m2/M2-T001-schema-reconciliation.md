# M2-T001: schema reconciliation with M1 run artifacts

## Milestone
M2: Supabase / control-plane foundation.

## Goal
Reconcile the existing `supabase/migrations/0001_init.sql` schema with M1's
filesystem artifacts produced by `kca run init` / `kca run record-metric`.
Produce `supabase/migrations/0002_kca_run_alignment.sql` that closes the gaps
without breaking the existing schema.

## Read first
1. `supabase/migrations/0001_init.sql`
2. `tools/kca/run.py` (current meta.json / metrics.json shape)
3. `docs/milestones/README.md` (M2 section)
4. `docs/adr/0002-hybrid-worker-model-routing.md`
5. ADR-004 in `docs/design-decisions.md` (code/git, artifacts/storage, metadata/Postgres)

## Mapping gaps (M1 artifact → DB)
- `meta.competition` (slug) ↔ `competitions.slug` — needs upsert pattern.
- `meta.run_id` (string timestamp) ↔ no DB column → add `experiment_runs.external_run_id text`.
- `meta.hypothesis` ↔ `experiments.hypothesis` exists, but `experiments.name` is NOT NULL — caller must supply both.
- `meta.tags` ↔ none → add `experiments.tags text[] not null default '{}'`.
- `runs/<comp>/<run_id>/` directory ↔ none → add `experiment_runs.run_dir text`.
- `metrics.json` records each metric's `recorded_at` ↔ `experiment_runs.metrics` jsonb is lossy → add an event table `experiment_run_metrics`.
- Local kca calls without a pre-created project ↔ `experiments.project_id` NOT NULL → insert a deterministic bootstrap project row.

## Required deliverables
- `supabase/migrations/0002_kca_run_alignment.sql`
- `docs/tooling/m2-schema-changes.md` summarizing the diff in prose.
- The migration is forward-only (no destructive drops); idempotent where reasonable.

## Design constraints
- Pure DDL + a single seed `insert ... on conflict do nothing` for the bootstrap project.
- No data backfill yet (M1 filesystem state will be re-recorded by T004's writers).
- Keep RLS enabled on new tables; real policies wait for M2/M3.
- No changes to existing enums; do not alter existing columns.

## Non-goals
- Do not write the Python writer (M2-T004).
- Do not run `supabase db push` (M2-T002 covers local apply).
- Do not add Storage buckets (M2-T006 owns this decision).

## Acceptance criteria
- `0002_kca_run_alignment.sql` exists and is syntactically valid (parses with `psql --dry-run` if available, otherwise reviewed for syntax).
- Migration adds at least: `experiment_runs.external_run_id`, `experiment_runs.run_dir`, `experiments.tags`, `experiment_run_metrics` table, bootstrap `projects` row, unique index on `(experiment_id, external_run_id)`.
- `docs/tooling/m2-schema-changes.md` lists every new column/table with a one-line rationale and points to the M1 field that motivated it.

## Suggested checks
```bash
test -f supabase/migrations/0002_kca_run_alignment.sql
grep -E 'create table experiment_run_metrics|external_run_id|run_dir|tags text' supabase/migrations/0002_kca_run_alignment.sql
# If postgres is available locally:
psql -U postgres -d postgres -1 -f supabase/migrations/0002_kca_run_alignment.sql --set ON_ERROR_STOP=on
```

## Stop condition
Stop after 30 turns if the existing schema has constraints that conflict
irreconcilably with M1 — record the conflict in `docs/tooling/m2-schema-changes.md`
under "Blockers" and propose the minimum schema change that breaks them.
