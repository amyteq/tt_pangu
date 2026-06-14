# M11-T006: Reviewer gate fires for `challenge_run` and `flag_submit`

## Milestone
M11: authorized CTF / lab workflow.

## Goal
Exercise the reviewer-gate path for **both** new ops end-to-end —
`challenge_run` (before invoking a solver against an authorized target)
and `flag_submit` (before submitting a flag). Each gate writes an
`agent_reviews` row + `human_decisions` row; the `decision_api` exposes
both pending decisions to the UI Approval Inbox; the human approves both
via `kca decisions approve --id <id>` (NOT via real external calls).

The real flag submission to a live event is **out of scope** for T006 —
that's T007. T006 closes with the round-trip recorded for both ops, but
the actual external POST is not made.

## Read first

1. M11-T002 closeout (the new ops + worker wiring)
2. M11-T005 closeout (solver loop, gates OFF)
3. `src/worker/reviewer.py`
4. `services/decision_api/app.py`
5. `tools/kca/decisions.py`
6. `supabase/migrations/0006_m6_reviews_spans.sql` (agent_reviews shape)
7. `ui/src/pages/ApprovalInbox.tsx`, `ui/src/pages/DecisionGate.tsx`
8. `docs/tasks/m9/M9-T003-reviewer-approval-gate.md` — `kaggle_submit`
   precedent
9. `docs/tasks/m10/M10-T003-kernel-push-reviewer-gate.md` — `kernel_push`
   precedent
10. Issue #15 — no `GET /decisions` endpoint (work around as M9/M10 did)
11. Issue #16 — `reviewer_decision` event_type wording drift

## Scope

1. **Drive `challenge_run` to the gate.** Re-run the bundled-web-
   challenge solve from T005, this time WITHOUT `--dry-run`. The
   worker reaches the point where it would invoke the solver against
   `localhost:<port>` (in scope per the web challenge's `ctf_scopes`
   row). The reviewer-gate fires; `agent_reviews` row written with
   `target_op="challenge_run"`; `human_decisions` row created via
   `decision_api`. The agent halts waiting for approval.

2. **Approve `challenge_run`.** `kca decisions approve --id <id>` (or
   via the UI Approval Inbox). The worker resumes, invokes the solver,
   recovers the flag, records the attempt. Verify the second
   `ctf_attempts` row for this challenge has the gate's review-id
   linkage (via `agent_job_events`).

3. **Drive `flag_submit` to the gate (LOCAL_WRITE only).** Invoke
   `kca ctf flag submit --event <past-event-slug> --challenge <web-
   slug> --flag-file <path-to-recovered-flag>`. Because the chosen
   event is the **past** event from T004 (no live endpoint), the
   command must:
   - Fire the `flag_submit` reviewer-gate.
   - When approved, refuse to actually POST (no live endpoint;
     `remote_endpoint=null` in `challenge.yaml`).
   - Record a `ctf_attempts` row with `http_status=null` and a
     `response_excerpt` noting "dry-run path; no remote endpoint".
   - Confirm the gate fired even though no real network call follows.

4. **Approve `flag_submit`.** Same approval path. Confirm the
   `human_decisions` row + the `agent_job_events` linkage.

5. **Smoke the refusal direction.** With the gates ON, attempt a
   challenge_run against `http://kaggle.com` (a host NOT in any
   `ctf_scopes.target_urls` row). Expected:
   - `network_egress` denies the call at the reviewer-gate layer.
   - `agent_reviews.verdict=reject` recorded.
   - The worker halts and does NOT attempt the call.

## Non-goals

- Do not make any real external network call to a CTF event API. T007
  owns that single call.
- Do not approve any decision without the human's explicit
  `kca decisions approve` invocation.
- Do not modify `services/decision_api/app.py` to add `GET /decisions`
  — that's issue #15's scope.
- Do not change the `target_op` wording emitted by the worker — that's
  issue #16's scope.

## Acceptance criteria

- `agent_reviews` has at least 2 new rows with
  `target_op in ('challenge_run','flag_submit')`.
- `human_decisions` has at least 2 new rows matching the reviews
  (target_op aligned).
- `agent_job_events` has the linking events for both round-trips.
- The challenge_run gate's verdict is `approve`; the worker resumed
  and recovered the flag.
- The flag_submit gate's verdict is `approve`; the LOCAL_WRITE-only
  `ctf_attempts` row was recorded with `http_status=null`.
- The refusal smoke (challenge_run against `kaggle.com`) recorded
  `agent_reviews.verdict=reject` and the worker did NOT POST.
- No flag value or credential value appears in `agent_reviews.context`
  or `human_decisions.notes`.
- UI Approval Inbox renders both pending decisions during the test
  window (manually verified; screenshot optional, link in closeout).

## Permissions

- LOCAL_WRITE DB inserts.
- `dangerouslyDisableSandbox=true` for DB / `localhost` calls.
- `kca decisions approve --id <id>` invocations.
- No real external network calls.

## Closeout format

```
M11-T006 closeout
  challenge_run round-trip: agent_reviews.id=<uuid>; human_decisions.id=<uuid>; verdict=approve
  flag_submit round-trip: agent_reviews.id=<uuid>; human_decisions.id=<uuid>; verdict=approve; ctf_attempts.id=<uuid> (http_status=null)
  Refusal smoke (challenge_run → kaggle.com): agent_reviews.verdict=reject; no POST
  agent_job_events linkage: <n> events tying job <id> to the two reviews
  UI Approval Inbox: pending decisions visible (manual check; <link or 'verified locally'>)
  Audit-grep for flag/credential leakage in review context: 0 hits
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T007 ready to start
```

## Related issues

- M11 proposal issue (TBD). M11-T006 closes the "reviewer gate round-
  trip" bullet.
- Cross-link issue #15 / #16 (worked around, not closed).

## Stop condition

Stop after 80 turns. If the gate fails to fire when it should, halt
and re-check `src/worker/reviewer.py::should_consult_reviewer` from
T002. If the refusal smoke does NOT deny `kaggle.com`, halt and
re-check the `network_egress` policy resolution — that is a
security-critical bug and blocks the milestone.
