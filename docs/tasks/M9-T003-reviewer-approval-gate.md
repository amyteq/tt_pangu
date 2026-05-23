# M9-T003: Reviewer gate + approval inbox

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Drive the worker to the point where `kaggle_submit` is the next action.
The M6 reviewer gate must fire, writing an `agent_reviews` row and a
pending `human_decisions` row. The decision_api surfaces the pending
decision and the UI Approval Inbox renders it. A human approves via
`kca decisions approve` (M9-T003 only — M9-T004 runs the real submit).

This task assumes **M9-T002 closeout is PASS** with a staged
`submission.csv`.

## Read first

1. M9-T002 closeout
2. `src/worker/reviewer.py`
3. `services/decision_api/app.py`
4. `tools/kca/decisions.py`
5. `supabase/migrations/0006_m6_reviews_spans.sql`
6. `ui/src/pages/ApprovalInbox.tsx`, `ui/src/pages/DecisionGate.tsx`
7. `docs/architecture/m8-ui-shell.md`

## Scope

1. Re-invoke the worker with the staged submission and a
   `kaggle_submit`-bound next action.
2. Confirm the reviewer-gate fires:
   - row written to `agent_reviews`;
   - row written to `human_decisions` with `status='pending'`;
   - event written to `agent_job_events`.
3. Confirm the decision_api `GET /decisions?status=pending` returns the
   row.
4. Confirm the UI Approval Inbox shows the pending decision when run
   locally (`pnpm -C ui dev`, open `/inbox`).
5. Approve via `kca decisions approve --id <decision_id> --note
   "M9-T003 dry approval; real submit happens in T004"`.
6. The approval should **not** trigger a real `kaggle competitions submit`
   here — verify by inspecting the worker stop reason.

## Non-goals

- Do not run a real `kaggle competitions submit`. T004 is the only
  Loop Prompt that does.
- Do not change `services/decision_api/` auth model.
- Do not change `tools/kca/decisions.py` semantics — observe only.
- Do not introduce a new approval policy class.

## Acceptance criteria

- `agent_reviews` row exists for the M9 run.
- `human_decisions` row exists with `status='pending'` then `approved`.
- `agent_job_events` shows the `reviewer_decision` event.
- `kca decisions list --json` shows the approved row.
- `services/decision_api/tests/test_decision_api.py` still passes
  (regression).
- Approval gate did NOT auto-trigger a real Kaggle submit (the closeout
  must state how this was verified — e.g. worker stopped on
  `policy_violation` or `pending_submission`).

## Permissions

- DB read/write via `dangerouslyDisableSandbox=true` only.
- Local UI dev server is allowed.
- No `kaggle competitions submit`.
- `git commit` / `git push` deferred to milestone closeout.

## Closeout format

```
M9-T003 closeout
  agent_reviews.id: <uuid>
  human_decisions.id: <uuid>  status: approved
  agent_job_events: <count> events written (reviewer_decision present)
  decision_api GET /decisions: pending=0 after approve
  UI render verified: YES | NO
  Real submit triggered? NO  (verified via worker stop reason: <reason>)
  Acceptance: PASS | FAIL — link to issue
  Next: M9-T004 BLOCKED on a `decision:confirmed` comment for real submit
```

## Stop condition

Stop after 60 turns. If the reviewer-gate does NOT fire, do NOT continue
to T004 — investigate first.
