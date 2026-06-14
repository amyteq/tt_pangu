# M8-T005: Dashboard page

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 5; extracted here for the double-layer convention.

## Goal
Implement the Dashboard page — overview of projects, active competitions,
and currently running / pending jobs.

## Read first
1. `ui/src/lib/db.ts` (typed query functions)
2. `ui/src/components/Layout.tsx`
3. `supabase/migrations/0001_init.sql` (projects, competitions)
4. `supabase/migrations/0003_m3_worker.sql` (agent_jobs)
5. `supabase/migrations/0006_m6_reviews_spans.sql` (telemetry, reviews)

## Scope / Files / Implementation guidance

### `ui/src/pages/Dashboard.tsx`
Sections:
1. **Projects** — Card grid (one per project), shows competition count
   and last-active job timestamp.
2. **Active competitions** — Table of `competitions` where there is
   at least one job in the last 30 days. Columns: slug, name, repo,
   open runs, last CV score, last submission status.
3. **Inflight runs** — Table of `agent_jobs WHERE status IN
   ('queued','running','awaiting_decision')`. Columns: skill_name,
   status, started_at, turns_used, cost_so_far, link to RunTimeline.
4. **Recent decisions** — last 10 rows from `human_decisions`, with
   a green pill for approved, red for rejected, amber for pending.

### UI rules
- Every list section uses `<Empty />` when there is no data.
- Every loading state uses `<Spinner />`, never a blank screen.
- Never call mutating endpoints from this page.

## Acceptance criteria
- `cd ui && pnpm test -- --run` → page test asserts the four sections
  render with mock data (use vitest + RTL with a stubbed supabase client;
  do NOT call the real DB in unit tests).
- Manual smoke (requires running DB):
  ```bash
  cd ui && pnpm dev &
  curl -s http://localhost:5173/ | grep -q "Projects"
  curl -s http://localhost:5173/ | grep -q "Active competitions"
  curl -s http://localhost:5173/ | grep -q "Inflight runs"
  curl -s http://localhost:5173/ | grep -q "Recent decisions"
  pkill -f "vite" || true
  ```
- `cd ui && pnpm typecheck` → 0 errors
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: section presence, vitest results, typecheck status.

## Stop condition
Stop after 30 turns.
