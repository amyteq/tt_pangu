# M8-T006: Run Timeline + event log

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 6; extracted here for the double-layer convention.

## Goal
Render a single agent job as a swim-lane timeline of OTEL spans plus a
paginated event log on the right.

## Read first
1. `supabase/migrations/0003_m3_worker.sql` (`agent_job_events` shape)
2. `supabase/migrations/0006_m6_reviews_spans.sql` (`agent_telemetry_spans`, OTEL)
3. `src/worker/telemetry.py` (span fields populated)
4. `ui/src/lib/db.ts` (`listJobEvents`, `listJobSpans`)

## Scope / Files / Implementation guidance

### `ui/src/pages/RunTimeline.tsx`
- Route: `/runs/:jobId`
- Top: Job summary card — `skill_name`, `status`, `turns_used`, `cost_so_far`,
  `started_at` / `ended_at`, link to project + competition.
- Middle: SVG swim-lane:
    - One row per `span.name` (or grouped by `span.attributes.kind`:
      job / turn / tool / reviewer / local-probe).
    - X axis: elapsed time since job start.
    - Hover tooltip: span name + duration + attributes JSON.
    - Color: green=ok, red=error, amber=in-progress.
    - Use a simple `<svg>` render — no D3, no recharts here.
- Right rail: paginated event log from `agent_job_events`.
    - Filter by `event_type` (`tool_call`, `decision_request`, `review_verdict`,
      `budget_warning`, `error`).
    - Each row: `ts | event_type | summary | expand-to-JSON`.

### UI rules
- The page is read-only. No buttons that emit writes.
- Empty job → render `<Empty />` with link back to `/runs`.

## Acceptance criteria
- `cd ui && pnpm test -- --run` → page test renders 3 mock spans into a
  swim-lane and asserts the row count.
- `cd ui && pnpm typecheck` → 0 errors
- Manual smoke (requires running DB with at least one job from Prompt 3's
  end-to-end smoke):
  ```bash
  cd ui && pnpm dev &
  JOB_ID=$(psql "$SUPABASE_DB_URL" -t -A -c \
    "SELECT id FROM agent_jobs ORDER BY started_at DESC LIMIT 1;")
  curl -s "http://localhost:5173/runs/$JOB_ID" | grep -q "skill"
  pkill -f "vite" || true
  ```
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: swim-lane rendered, span count, event log row count.

## Stop condition
Stop after 30 turns.
