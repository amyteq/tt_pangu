# M8-T007: Experiments / Runs table

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 7; extracted here for the double-layer convention.

## Goal
A sortable, filterable table of experiments and runs across competitions,
with a drill-down to per-run metrics.

## Read first
1. `supabase/migrations/0004_m4_competition_repo.sql` (experiments, runs, submissions)
2. `ui/src/lib/db.ts` (`listExperiments`, `listRunsForCompetition`)
3. `ui/src/pages/Dashboard.tsx` (table style to mirror)

## Scope / Files / Implementation guidance

### `ui/src/pages/Experiments.tsx`
Header filters: competition slug, status, "show submitted only".

Table columns:
- Experiment ID + name
- Competition
- Last run ts
- CV score (best of `runs.metric_value` where `metric_name = cv_score`)
- LB score (latest `submissions.public_score`)
- Status badge
- link to `/runs/:jobId` for the latest run

Sortable by: ts desc (default), CV asc/desc, LB asc/desc.
Pagination: 25 per page, server-side via Supabase `.range(...)`.

### `ui/src/pages/RunDetail.tsx` (route: `/experiments/:experimentId`)
- Lists all runs for the experiment.
- For each run: ts, metric_name, metric_value, artifact link.
- Links to the run timeline page.

### UI rules
- Sortable column headers must be keyboard accessible.
- Numeric columns right-aligned, monospace.

## Acceptance criteria
- `cd ui && pnpm test -- --run` → sort + filter logic tests pass with mock
  data; column count matches spec.
- `cd ui && pnpm typecheck` → 0 errors
- `cd ui && pnpm build` → 0 errors
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: column list, sort tests, build size.

## Stop condition
Stop after 30 turns.
