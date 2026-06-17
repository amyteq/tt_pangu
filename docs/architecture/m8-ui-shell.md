# M8 UI Shell Architecture

_Status: M8 (2026-05-23)._

## Overview

M8 surfaces the M2–M7 control plane as a read-mostly operator workbench.
The browser is a Vite + React + TypeScript SPA that talks to Supabase
for reads (via the JS client + anon key + RLS) and to a small Python
FastAPI **decision_api** service for the three write paths a human ever
performs in the UI: approve, reject, ask-the-agent-to-improve. The
browser bundle never holds a service-role key; every mutation flows
through `services/decision_api/` which re-uses the existing
`tools/kca/decisions.py` functions and writes through
`tools/kca/db.py`, so the M7 permission policy resolution stays
authoritative.

## Layer map

```
+---------------------------+        +-------------------------+
|        Browser (SPA)      |        |   FastAPI action svc    |
|  Vite + React + RR        |        |   services/decision_api |
|                           |        |                         |
|  read path: @supabase/js  |        |  POST /decision/:id/*   |
|  write path: /api/*       |  --->  |       │                 |
+-----------┬---------------+        +-------┼-----------------+
            │                                 │
            ▼                                 ▼
        Postgres                        tools/kca/decisions.py
        (anon key,                            │
         RLS-gated)                           ▼
                                        tools/kca/db.py
                                              │
                                              ▼
                                         Postgres
                                              │
                                              ▼
                                  agent worker resume
                                  (src/worker/worker.py)
```

## Data flow per page

| Page                | Tables read                                          | Joins                                              |
|---------------------|------------------------------------------------------|----------------------------------------------------|
| Dashboard           | `projects`, `competitions`, `agent_jobs`, `human_decisions` | none (four parallel lists)                         |
| RunTimeline         | `agent_jobs`, `agent_job_events`, `agent_telemetry_spans` | `agent_telemetry_spans.job_id → agent_jobs.id`     |
| Experiments         | `experiments`, `experiment_runs`, `submissions`     | runs/subs filtered client-side per experiment id   |
| Research            | `research_items`, `research_citations`               | citations selected by `run_id` of the active item  |
| ApprovalInbox       | `human_decisions` where `status='pending'`           | none                                               |
| DecisionGate        | `human_decisions`, `agent_jobs`, `agent_reviews`, `agent_tool_audit` | reviews + audit joined on `job_id`                 |
| Artifacts           | `artifacts`                                          | filters resolved client-side (job_id metadata)     |

Every query in `ui/src/lib/db.ts` returns a typed `Promise<T[]>` or
`Promise<T | null>` and handles the no-rows case explicitly. The supabase
client falls through to an empty-array fake when `VITE_SUPABASE_ANON_KEY`
is empty so the SPA still renders cleanly in tests and demo previews.

## Auth model

- M8 ships **single-user, local-only**.
- The decision_api accepts a shared token in
  `KCA_DECISION_API_TOKEN`; the browser supplies it via the
  `X-Decision-Api-Token` header. The token is set out-of-band by
  `kca ui login`, which writes a same-origin `kca_api_token` cookie.
- Reads from Supabase use the **anon key** + RLS. The browser never sees
  a service-role key. If anon access is too permissive for a future
  deployment, the read path should swap to Supabase RPC functions with
  `security_definer` views — that work lands in M9+.
- A grep over `ui/` for `SERVICE_ROLE` must return zero matches; this is
  enforced both by exit-criteria check #21 and by the CI `ui` job.

## Approval gate semantics

- The UI calls **three** action endpoints; nothing else:
  - `POST /decision/:id/approve` — body: `{reason?: string}`.
  - `POST /decision/:id/reject` — body: `{reason: string}` (≥ 8 chars,
    enforced by Pydantic).
  - `POST /decision/:id/ask-improve` — body:
    `{feedback: string, metric_target?: string}`.
- Each endpoint:
  1. Verifies the `X-Decision-Api-Token` if `KCA_DECISION_API_TOKEN`
     is set on the server (test runs may skip the token check).
  2. Reads the `human_decisions` row. If it isn't `status='pending'`,
     returns **409 Conflict** — decisions are atomic.
  3. Calls `tools/kca/db.py::resolve_decision` for the appropriate
     terminal status (`approved` / `rejected` / `needs_improvement`).
  4. For `ask-improve`, additionally appends an
     `agent_job_events("feedback")` row so the worker picks it up on
     resume.
  5. Writes an `agent_tool_audit` row via
     `tools.kca.agent.audit.log_policy_decision`.
- The browser cannot construct a `kaggle competitions submit`
  invocation. It can only set the decision status; the actual
  submission still flows through the worker after the approval is
  recorded, and that worker is gated by the M7 permission policy.
- DecisionGate UI rule: the **Approve** button is `bg-red-600`
  (`variant="danger"`) when the operation is in the submission set
  (`kaggle_submit`, `kernel_push`, `supabase_migrate`, `git_push`).
  All other operations get `bg-amber-500` (`variant="caution"`). This
  forces a visual pause before a destructive approve.

## Audit trail

- Every action service mutation writes to `agent_tool_audit` via
  `tools.kca.agent.audit.log_policy_decision`.
- `.agent/kca/audit.jsonl` (ADR-0021; formerly `.agent/audit.jsonl`) continues
  to exist for offline ops; the dual-write behaviour from M8-T001 keeps both
  backends in sync when a
  DB is configured. The writer never raises on DB failure — JSONL is
  the source of truth.
- The DecisionGate page surfaces the last 20 audit rows for the job
  under review, so a human can see "what did the agent already touch?"
  before approving the next step.

## Adding a new page

1. Add the route to `ui/src/routes.tsx`.
2. Add a typed query function in `ui/src/lib/db.ts`. Reuse the
   `rows<T>(…)` / `maybeOne<T>(…)` helpers — they ensure no-rows is
   handled explicitly.
3. Create the page component under `ui/src/pages/`. Use the existing
   `ui/src/ui/*` primitives (`Card`, `Table`, `Badge`, `Empty`,
   `Spinner`) — no design-system dep.
4. Write a vitest unit test under `ui/src/pages/<Page>.test.tsx` that
   mocks `../lib/db` and asserts the section renders. (See
   `Dashboard.test.tsx` for the canonical pattern.)
5. Optional: extend `ui/tests/e2e/m8.spec.ts` with a Playwright case
   that visits the route and asserts the heading. The dev server +
   fake supabase client are already in place.

## Adding a new approve-class operation

1. Add a `ToolSpec` entry in `tools/kca/agent/tool_registry.py`,
   including its `side_effect`, `approval_label`, `sandbox`, and
   `timeout_s`.
2. Update the relevant permission profile under `.kca/permissions/` so
   the new operation has a default decision per mode.
3. Wire the worker behavior: nothing usually needed — the M8
   `_tool_call` already routes any tool through
   `JobPolicy.tool_decisions[tool_name]` + ToolSpec enforcement.
4. Render in `DecisionGate.tsx`: extend `SUBMISSION_OPERATIONS` set if
   the new op should get the red destructive button.
5. Add a smoke test in `tests/test_m8_smoke.py` (or a dedicated
   `tests/test_m9_*.py` for new milestones) that exercises the
   approve/reject path.
6. Document the new gate in this file's "Approval gate semantics"
   section.
