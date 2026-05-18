# M2 schema changes (migration 0002)

Migration file: `supabase/migrations/0002_kca_run_alignment.sql`.

This migration aligns the M0-drafted schema (`0001_init.sql`) with the
artifacts the M1 `kca` CLI actually produces, so the DB can become the
source of truth for runs (per the decision recorded for M2-T004).

## What changed and why

| Change | Motivated by (M1 artifact) | Rationale |
|---|---|---|
| Seed row `projects.id = 00000000-…-0001` (`local-default`) | `kca run init` has no project concept | Lets local kca calls write without first creating a project. The fixed UUID is a namespace constant the Python client can reference directly. |
| `experiment_runs.external_run_id text` | `meta.json.run_id` (`"20260517_101109"`) | DB primary keys stay UUID; M1's human-readable timestamp lives in a separate column. |
| `experiment_runs.run_dir text` | filesystem path `runs/<comp>/<run_id>/` | Lets the DB row point back at its filesystem cache; needed for `kca run record-metric --run-dir`. |
| Partial unique index `uq_experiment_runs_external` on `(experiment_id, external_run_id) where external_run_id is not null` | one external_run_id per experiment | Prevents accidental dupes; partial so legacy NULL rows don't collide. |
| Index `idx_experiment_runs_run_dir` | path-based lookups | Used to resolve `--run-dir` arg → row. |
| `experiments.tags text[] default '{}'` | `meta.json.tags` | Tags are first-class enough to query directly rather than burying in jsonb. |
| Table `experiment_run_metrics` (append-only) | `metrics.json` records `recorded_at` per metric | The existing `experiment_runs.metrics jsonb` is last-value-wins; this table preserves history. Both stay in sync (M2-T004 writes to the event table and refreshes the jsonb). |
| Indexes on `experiment_run_metrics(experiment_run_id, recorded_at desc)` and `(key)` | metric history / cross-run comparison queries | Cheap, expected query patterns. |
| Index `idx_competitions_slug` | `kca run list --competition <slug>` | Slug-only lookups are common; the existing `(platform, slug)` unique is a superset but less direct. |
| Indexes `idx_human_decisions_status_created` and `(decision_type, status)` | M2-T005 approval recording | Enables a fast "pending approvals" inbox query. |
| Column / table comments | Studio readability | When humans browse the schema in Supabase Studio, the columns explain themselves. |

## What did NOT change (deliberately)

- No alterations to existing columns or enums in `0001_init.sql`. Forward-only.
- No drops of any kind.
- No new RLS policies — RLS is enabled on the new table but policies wait for the auth model (M3+).
- No data backfill from existing `runs/` filesystem state. M1 run dirs are treated as legacy; M2-T004's writers start fresh.
- No artifact-related changes — `artifacts.storage_path` semantics are decided in M2-T006 (ADR-007), not a schema change.
- No worker / job queue alterations — `agent_jobs` already has enough structure; M3 owns worker wiring.

## Idempotence

The migration is safe to run multiple times:
- The bootstrap project insert uses `on conflict (id) do nothing`.
- All `alter table` use `add column if not exists`.
- All `create index` use `if not exists`.
- `create table experiment_run_metrics` uses `if not exists`.

A `supabase db reset` followed by `supabase db push` (or `db reset --debug`) will rebuild from scratch cleanly.

## Open questions for M2-T003 / T004

- Should `competitions.platform` be defaulted to `'kaggle'` at the kca call site, or threaded through as an arg? Current default in the table is `'kaggle'`, so kca can omit it; revisit when CTF gets first-class run support.
- Should `experiments.name` be derived from `external_run_id` (current plan) or from the hypothesis text? Tradeoff: stable IDs vs. human-readable. Plan: use `external_run_id` for name; surface hypothesis separately. Revisit if the UI shell needs a friendlier display.

## Blockers

None identified. The existing schema is permissive enough that M2's needs fit additively.
