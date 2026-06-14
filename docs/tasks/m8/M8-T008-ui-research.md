# M8-T008: Research page

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 8; extracted here for the double-layer convention.

## Goal
Surface the M5 research items and citations so a human can audit what the
agent read.

## Read first
1. `supabase/migrations/0005_m5_research_citations.sql`
2. `tools/kca/research.py` (trust labels, source URL fields)
3. `ui/src/lib/db.ts` (`listResearchItems`, `listCitationsForRun`)

## Scope / Files / Implementation guidance

### `ui/src/pages/Research.tsx`
Left rail: research items list, newest first. Each row shows:
- title / source URL (link opens in new tab with `rel="noopener noreferrer"`)
- trust label (badge: green=high, amber=medium, red=low/unknown)
- `related_run_id` link
- `fetched_at` ts

Main panel: when an item is selected:
- rendered Markdown summary
- citations table: `run_id`, span snippet, similarity, link to `/runs/:jobId`
- "raw source" disclosure (collapsed by default; expands to the stored
  DOM snapshot path under `artifacts/research/`)

### UI rules
- All external URLs open in a new tab, `rel="noopener noreferrer"`.
- Markdown render uses a strict sanitiser (no inline JS, no remote images
  by default — show "load image" placeholder).
- Never auto-fetch external content from the browser; only display what
  is already in the DB / artifacts.

## Acceptance criteria
- `cd ui && pnpm test -- --run` → sanitiser test asserts `<script>` tags
  are stripped; `rel` attributes present on `<a>`.
- `cd ui && pnpm typecheck` → 0 errors
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: sanitiser test, trust label colours, external link rel attribute count.

## Stop condition
Stop after 30 turns.
