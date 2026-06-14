# M8-T010: Artifact Browser

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 10; extracted here for the double-layer convention.

## Goal
A read-only artifact browser. Lists artifacts by job/run and previews
small text files inline; binaries get a download link only.

## Read first
1. `supabase/migrations/0001_init.sql` (artifacts table)
2. `docs/adr/` (artifact storage ADR)
3. `ui/src/lib/db.ts` (`listArtifacts`)

## Scope / Files / Implementation guidance

### `ui/src/pages/Artifacts.tsx`
Filters: `job_id`, competition slug, `artifact_type`.
Table columns: `path`, `type`, `size`, `sha256` (first 12 chars),
`created_at`, run link.

### `ui/src/pages/ArtifactDetail.tsx` (route `/artifacts/:id`)
- Show metadata.
- If text and size < 1 MB: inline preview via `<pre>` with a content-type
  guess (utf-8 only). For CSV: a first-100-rows table render.
- If binary or > 1 MB: download link only. Show a clear warning.
- Never preview `.pkl`, `.pt`, `.h5`, `.bin`, `.so` — always download-only.

## Acceptance criteria
- `cd ui && pnpm test -- --run` → size-cap test, binary extension blocklist
  test, CSV 100-row cap test.
- `cd ui && pnpm typecheck` → 0 errors
- `cd ui && pnpm build` → 0 errors
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: blocklist enforced, size cap honoured, build OK.

## Stop condition
Stop after 30 turns.
