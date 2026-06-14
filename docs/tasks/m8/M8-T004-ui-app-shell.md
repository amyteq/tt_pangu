# M8-T004: UI app shell + read-only data client

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 4; extracted here for the double-layer convention.

## Goal
Build the app shell — top nav, side nav, theme, error boundary, routing,
and a typed Supabase data client.

## Read first
1. `ui/src/App.tsx` (placeholder from Prompt 0)
2. `ui/src/lib/supabase.ts` (from Prompt 0)
3. `docs/architecture/kca-cli-architecture.md` (mental model for layers)
4. `supabase/migrations/0001..0007` (table shapes for typed queries)

## Scope / Files / Implementation guidance

### Step 1 — Routing
- `ui/src/main.tsx`: wrap `App` in `BrowserRouter`.
- `ui/src/routes.tsx`: declare routes:
  ```
  /                  → Dashboard
  /runs              → Runs
  /runs/:jobId       → RunTimeline
  /experiments       → Experiments
  /research          → Research
  /approvals         → ApprovalInbox
  /approvals/:id     → DecisionGate
  /artifacts         → Artifacts
  ```

### Step 2 — Layout
`ui/src/components/Layout.tsx`:
- Header: project name, environment badge (local/dev/prod from
  `VITE_KCA_ENV`), GitHub link, "M8 preview" pill.
- Side nav: links to the seven pages above with active-route highlight.
- `<Outlet />` for nested routes.

`ui/src/components/ErrorBoundary.tsx`: catches render errors, shows the
stack in dev, a friendly message in prod.

### Step 3 — Typed data client
`ui/src/lib/db.ts`:
- Define narrow TypeScript types for each table the UI reads:
  `Project`, `Competition`, `AgentJob`, `AgentJobEvent`, `AgentTelemetrySpan`,
  `Experiment`, `Run`, `Submission`, `ResearchItem`, `ResearchCitation`,
  `HumanDecision`, `AgentReview`, `Artifact`, `AgentToolAudit`.
- Each function returns `Promise<T[]>` or `Promise<T|null>`:
  `listProjects`, `getProject`, `listCompetitions`,
  `listRecentRuns`, `listRunsForCompetition`,
  `getJob`, `listJobEvents`, `listJobSpans`,
  `listExperiments`, `listSubmissions`,
  `listResearchItems`, `listCitationsForRun`,
  `listPendingDecisions`, `getDecision`, `listReviewsForJob`,
  `listArtifacts`, `listToolAudit`.
- Each function uses the Supabase JS client; no raw SQL strings.
- Every function MUST handle the "no rows" case explicitly.

### Step 4 — Generic UI primitives (no design-system dep)
`ui/src/ui/{Button,Card,Table,Badge,Empty,Spinner,Modal,Toast}.tsx`

Tailwind-only, no JS state unless necessary.

## Acceptance criteria
- `cd ui && pnpm typecheck` → 0 errors
- `cd ui && pnpm build` → 0 errors
- `cd ui && pnpm dev &` → `:5173`
- `curl -s http://localhost:5173/ | grep -q "kaggle-code-agent"`
- `curl -s http://localhost:5173/approvals | grep -q "<html"`
- `pkill -f "vite" || true`
- Type-check coverage: `cd ui && pnpm exec tsc --noEmit --strict` → 0 errors
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: route count, typed query count, typecheck status.

## Stop condition
Stop after 30 turns.
