# M10-T003: Reviewer gate fires before `kernel_push`

## Milestone
M10: live end-to-end regression test — Petals to the Metal.

## Goal
Verify that the reviewer-gate flow fires correctly for the
`kernel_push` target_op, writes `agent_reviews` + `human_decisions`
rows, and surfaces the pending decision via the decision_api / UI
Approval Inbox. Approve the decision via `kca decisions approve`
(NOT via a real Kaggle kernel push).

This task assumes **M10-T000, M10-T001, M10-T002 closeouts are PASS**.

## Read first

1. M10-T002 closeout
2. `src/worker/reviewer.py`
3. `src/worker/worker.py` (event emission for the approval flow)
4. `services/decision_api/app.py`
5. `tools/kca/decisions.py`
6. `supabase/migrations/0006_m6_reviews_spans.sql`
7. `ui/src/pages/ApprovalInbox.tsx`, `ui/src/components/DecisionGate.tsx`
8. `docs/tasks/m9/M9-T003-reviewer-approval-gate.md` (the `kaggle_submit`
   precedent)
9. Issue #15 (decision_api: no `GET /decisions` endpoint — UI reads
   via supabase-js for the time being; do NOT block T003 on closing #15)
10. Issue #16 (`reviewer_decision` event_type drift — use the literals
    the worker actually emits; do NOT block T003 on closing #16)

## Scope

1. Drive a worker job that stages the baseline notebook + kernel-
   metadata.json (from M10-T002) toward `kca kaggle push`. The worker
   pauses at the reviewer-gate; the LLM reviewer abstains (drive via
   the same pattern as M9-T003 — monkey-patch the reviewer to
   `verdict="abstain"` if necessary, documented in the closeout).
2. Confirm:
   - `agent_reviews` row exists with `target_op="kernel_push"`. Record
     `id`.
   - `human_decisions` row exists with `status="pending"` and
     `decision_type="tool_approval"`. Record `id`.
   - `agent_job_events` records the approval-pause + reviewer-decision
     trail (whatever literals the worker emits — `reviewer_abstain` +
     `approval_pause` per M9; if #16 lands a unified `reviewer_decision`,
     use that).
3. Verify the decision_api round-trip:
   - Direct DB read via `kca decisions list --pending --job-id <jid>`
     returns the pending decision.
   - If `GET /decisions` is implemented (issue #15 closed), HTTP fetch
     it under the same token and assert the response shape matches.
4. Approve via `kca decisions approve --id <human_decisions.id>
   --rationale "M10-T003 dry approval; real push happens in T004"`.
   Confirm:
   - `human_decisions.status` flips to `"approved"`.
   - `human_decisions.decided_at` is populated.
   - The worker emits an `approval_resume` event (or whatever literal
     follows from #16's resolution).
5. **Do NOT call** `kca kaggle push` or `kaggle kernels push` in this
   prompt — that is M10-T004's single approved call. Audit `.agent/
   audit/tool-events.jsonl` (or equivalent) to confirm 0 lines match
   the real push command.

## Non-goals

- Do not call any real Kaggle write command.
- Do not file a GH issue from this prompt (remote writes are deferred
  to milestone close per protocol §5).
- Do not change `services/decision_api/app.py` to add `GET /decisions`
  — that's issue #15.
- Do not change `src/worker/worker.py` to rename event types — that's
  issue #16.

## Acceptance criteria

- `agent_reviews` row exists with `target_op="kernel_push"`. Record id.
- `human_decisions` row exists. Pre-approve: `status="pending"`.
  Post-approve: `status="approved"`, `decided_at` populated.
- `agent_job_events` has ≥ 1 row with whichever reviewer-decision
  literal the worker emits and ≥ 1 row each for `approval_pause` /
  `approval_resume` (or the unified equivalent).
- `kca decisions list --pending --job-id <jid>` shows the pending row
  before approve; empty for that job after approve.
- No real Kaggle write call ran (audit-grep clean).
- `services/decision_api/tests/test_decision_api.py` still passes
  (5/5).
- All baseline validation still passes (pytest, ruff, pnpm where
  available).

## Permissions

- `git commit` and `git push` deferred to milestone closeout.
- No real Kaggle calls.
- DB writes are LOCAL_WRITE; require `dangerouslyDisableSandbox=true`.

## Closeout format

```
M10-T003 closeout
  agent_reviews.id: <uuid>   (verdict=<abstain|approve|reject>, target_op=kernel_push)
  human_decisions.id: <uuid> status: <approved>  (rationale: "M10-T003 dry approval...")
  agent_job_events: <n> events written for job_id <uuid>
    [<list of event types emitted>]
  decision_api GET /decisions: <N/A or evidence>
  UI render verified: <YES | SKIP — DB-layer read path verified instead>
  Real push triggered? NO. Verified via:
    - Worker stop_reason = "approval_required"
    - Audit grep over .agent/audit/tool-events.jsonl: 0 lines matching `kaggle kernels push` or `kca kaggle push`
  Regression: pytest <n> passed / <n> skipped (matches M10-T002 baseline). ruff clean.
  Acceptance: PASS | FAIL — link to issue
  Next: M10-T004 BLOCKED on a `decision:confirmed` comment for real push
        (per protocol). LP4 may proceed once a human files / labels the
        closing GitHub issue with `policy:approval-required` + a
        "approved to push" comment.
```

## Related issues

- #12 — M10 proposal
- #15 — decision_api: no `GET /decisions` endpoint. If still open at
  T003 time, document via direct-DB-read evidence; do not block T003.
- #16 — `reviewer_decision` event_type drift. Use the literals the
  worker emits today; do not block T003.

## Stop condition

Stop after 60 turns. If the reviewer-gate does NOT fire when it should
(worker proceeds straight to `kca kaggle push` without writing
`agent_reviews` / `human_decisions`), HALT and surface — that is the
M9 rollback "reviewer gate fails to fire when it should" condition and
is a milestone-blocking bug.
