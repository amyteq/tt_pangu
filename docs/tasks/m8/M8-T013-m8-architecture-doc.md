# M8-T013: M8 architecture documentation

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 13; extracted here for the double-layer convention.

## Goal
Write `docs/architecture/m8-ui-shell.md`.

## Read first
1. `docs/architecture/kca-cli-architecture.md` (style template)
2. `ui/src/lib/db.ts` (data flow inventory)
3. `services/decision_api/app.py` (action service shape)
4. `supabase/migrations/0007_m8_tool_audit.sql` (audit table)

## Scope / Files / Implementation guidance

### Required sections

#### `## Overview`
One paragraph: M8 surfaces the M2–M7 control plane as a read-mostly UI.
The browser never writes to Supabase directly except through the
`decision_api` action service, which routes through the existing
`tools/kca/decisions.py` paths so M7 policy gates stay authoritative.

#### `## Layer map`
Diagram (ASCII) of:
```
Browser (Vite SPA) → Supabase JS (read) → Postgres
                  → /api/decision/* → decision_api → kca decisions → Postgres
                                                                     → worker resume
```

#### `## Data flow per page`
For each of: Dashboard, RunTimeline, Experiments, Research, ApprovalInbox,
DecisionGate, Artifacts — list the tables read and the joins performed.

#### `## Auth model`
- Local-only token via `KCA_DECISION_API_TOKEN`.
- M8 ships single-user; multi-user lands in M9 or later.
- No service-role key ever reaches the browser.

#### `## Approval gate semantics`
- "Approve" / "Reject" / "Ask agent to improve" map to existing
  `tools/kca/decisions.py` functions.
- The browser cannot mutate `agent_jobs.status` directly; only the
  action service can, and only via the kca decisions API.
- M7 `permission_policy.resolve_for_skill` is the source of truth for
  which operations need a decision; UI is purely a presentation layer.

#### `## Audit trail`
- Every action service mutation writes a row to `agent_tool_audit`.
- `.agent/audit.jsonl` continues to exist for offline ops; the dual-write
  behaviour from M8-T001 keeps both backends in sync when DB is available.

#### `## Adding a new page`
Step-by-step: add route → add typed query in `ui/src/lib/db.ts` →
add page component → write vitest test → optional Playwright case.

#### `## Adding a new approve-class operation`
Step-by-step: add `ToolSpec` to `TOOL_REGISTRY` (M7) → add policy record →
add `decision_api` wiring → render in DecisionGate.

## Acceptance criteria
- `test -f docs/architecture/m8-ui-shell.md`
- `wc -l docs/architecture/m8-ui-shell.md` → at least 100 lines
- For each heading: `"Overview"`, `"Layer map"`, `"Data flow per page"`,
  `"Auth model"`, `"Approval gate semantics"`, `"Audit trail"`,
  `"Adding a new page"`, `"Adding a new approve-class operation"` —
  `grep -q "$h" docs/architecture/m8-ui-shell.md` returns 0.
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: line count, section headings, any FAIL.

## Stop condition
Stop after 30 turns.
