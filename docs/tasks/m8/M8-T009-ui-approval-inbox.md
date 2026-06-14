# M8-T009: Approval Inbox + Decision Gate

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 9; extracted here for the double-layer convention.

## Goal
The most important M8 page. A human sees every pending decision, approves /
rejects / asks-the-agent-to-improve, and the write path goes through the
EXISTING `kca decisions` mechanism — the browser never bypasses the
permission policy.

## Read first
1. `supabase/migrations/0003_m3_worker.sql` (`human_decisions`)
2. `supabase/migrations/0006_m6_reviews_spans.sql` (`agent_reviews`)
3. `supabase/migrations/0007_m8_tool_audit.sql` (`agent_tool_audit`)
4. `tools/kca/decisions.py` (approve / reject CLI)
5. `tools/kca/agent/permission_policy.py` (decision semantics)
6. `docs/milestones/README.md` (M8 § Decision-gate UI requirements)

## Scope / Files / Implementation guidance

### Step 1 — `ui/src/pages/ApprovalInbox.tsx`
- List `human_decisions` where `status = 'pending'`.
- Columns: `operation`, `run_id` link, `requested_at`, `policy_profile`,
  `reviewer_verdict` (from `agent_reviews` if any), action link.
- Default sort: oldest first ("FIFO so nothing rots").

### Step 2 — `ui/src/pages/DecisionGate.tsx` (route `/approvals/:id`)
Show the full context required by the milestone spec:
- `operation`
- `cv_score` (joined from `runs.metric_value` where `metric_name='cv_score'`)
- `cost_so_far` (joined from `agent_jobs.cost_so_far`)
- artifact preview (top 50 lines if the file is text and < 1 MB; otherwise
  a download link only — never preview binaries inline)
- reviewer verdict + reasoning (from `agent_reviews`)
- recent tool audit entries for the job (from `agent_tool_audit`)

Three actions:
- **Approve** → POST to action service (Step 3) with reason field optional.
- **Reject** → POST with reason required (UI enforces `minLength=8`).
- **Ask agent to improve** → POST with a structured "feedback" payload
  (free text + optional `metric_target`). The backend appends to
  `agent_job_events` and resumes the job at the next planning turn.

All three actions disable buttons immediately and show a spinner until
the response comes back. On success, redirect to `/approvals`.

### Step 3 — Action service
Stand up a tiny FastAPI app at `services/decision_api/` (Python).
```
POST /decision/:id/approve
POST /decision/:id/reject
POST /decision/:id/ask-improve
```
Each endpoint:
- Validates the user (M8 ships local-only: simple HMAC over
  `KCA_DECISION_API_TOKEN`; UI reads token from a same-origin cookie
  set out-of-band by `kca ui login`).
- Calls the existing functions in `tools/kca/decisions.py`.
- Writes audit via `tools.kca.agent.audit.log_policy_decision`.

Wire pnpm dev's `vite.config.ts` to proxy `/api/*` to `localhost:8787`.

### UI rules
- The browser cannot construct a `kaggle competitions submit` call; it
  can only call `/decision/:id/approve`. The actual submit still flows
  through the worker after the approval is recorded.
- "Approve" button is RED-DESTRUCTIVE-style if the operation is
  SUBMISSION-class (`kaggle_submit`, `kernel_push`, `supabase_migrate`),
  AMBER-CAUTION-style otherwise.
- Decision changes are atomic: the API rejects with 409 if the decision
  is already non-pending.

## Acceptance criteria
- `cd ui && pnpm test -- --run` → DecisionGate tests assert button colour
  by operation class + the "minimum 8 chars" reason rule.
- Action service round-trip (offline; the API is mocked to not call real
  Kaggle): `python -m pytest services/decision_api/tests -v` → all pass
- Manual smoke:
  ```bash
  KCA_DECISION_API_TOKEN=dev-token \
    uvicorn services.decision_api.app:app --port 8787 &
  cd ui && pnpm dev &
  curl -s http://localhost:5173/approvals | grep -q "Approval Inbox"
  pkill -f "vite|uvicorn" || true
  ```
- `cd ui && pnpm typecheck` → 0 errors
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: 3 actions, 409 atomic rule, button colour rules, all tests green.

## Stop condition
Stop after 30 turns.
