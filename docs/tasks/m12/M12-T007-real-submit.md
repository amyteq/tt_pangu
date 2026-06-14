# M12-T007: ONE real Devpost submit under human approval

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Land exactly **ONE** real Devpost submission, under explicit human
approval, mirroring M9's `kaggle_submit` and M10's `kernel_push`
discipline. The reviewer-gate, decision_api, and Approval Inbox path
get the same regression treatment.

T007 is the only task in M12 that:
- Adds `tools/kca/devpost.py::cmd_submit`.
- Fires the `devpost_submit` reviewer gate.
- Performs a real Devpost write.

## Tag

`policy:approval-required`. Issue starts `ai:blocked`; promotes to
`ai:ready` only after the closing issue carries a human comment
"approved to submit".

## Pre-conditions before running

1. M12-T006 closeout shows a complete submission_pack at
   `runs/<slug>/<run_id>/submission_pack/`.
2. The closing issue has `policy:approval-required` AND a human
   comment explicitly approving the submission (this milestone's only
   such record).
3. Devpost credentials (or a stored session cookie / API token —
   whichever auth shape T003 / this task settled on) are present in
   `.env`; the closing issue records which auth shape is used. Never
   print the credential.
4. `tests/test_m12_e2e.py` (M12-T008) is **not yet** authoritative —
   it ships in T008 — but T007's own pre-flight check must include a
   dry-run of the same code path with the credentials absent, to
   confirm the refusal path works.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M12
3. `docs/milestones/m12/loop-prompts.md` Loop Prompt 7
4. M12-T003 closeout (devpost adapter READ_ONLY surface)
5. M12-T006 closeout (submission_pack contents)
6. `src/worker/reviewer.py`
7. `services/decision_api/app.py`
8. `tools/kca/decisions.py`
9. `supabase/migrations/0006_m6_reviews_spans.sql` (`agent_reviews`)
10. `docs/tasks/m9/M9-T004-real-submission.md` — Kaggle submit precedent
11. `docs/tasks/m10/M10-T004-real-kernel-push.md` — kernel-push precedent
12. `.claude/settings.json` — verify the `devpost` write op is on `ask`
13. `.claude/hooks/guard_tool.py` — confirm credential reads are gated

## Scope

1. Add `tools/kca/devpost.py::cmd_submit`:
   - Signature: `cmd_submit(slug: str, run_id: str, message: str,
     dry_run: bool = False) -> dict`.
   - Reads `runs/<slug>/<run_id>/submission_pack/` to assemble the
     payload (README, demo plan, source link, any video URL).
   - If `dry_run=True` or credentials missing, exit non-zero with a
     clean message and DO NOT touch the network. This is the path
     M12-T008 will assert.
   - Otherwise, POST / form-submit to Devpost (whichever auth shape
     T003 documented); poll the response for the submission URL.
   - Returns `{ "external_submission_id": str, "submission_url": str }`.
2. Wire `cmd_submit` into `tools/kca/kca.py` as `kca devpost submit`.
3. Worker integration:
   - The `hackathon-experiment-loop` skill from T004 now reaches the
     `devpost_submit` step. The reviewer-gate in `src/worker/reviewer.py`
     writes an `agent_reviews` row + `human_decisions` row with
     `target_op="devpost_submit"`.
   - `services/decision_api` exposes the pending decision (POST queue;
     UI reads via supabase-js until issue #15 lands a GET).
4. Human approves via `kca decisions approve --id <decision_id>` AND
   posts an "approved to submit" comment on the closing issue. The
   triage agent verifies the comment, sets `decision:confirmed` +
   `ai:ready`.
5. Execute exactly ONE real `kca devpost submit --slug <slug>
   --run-id <run_id> --message "<short message>"`.
6. Record the result in `submissions`:
   - `platform = 'devpost'` (new value; ADR-0018's policy supports it)
   - `external_submission_id = <id-from-cmd_submit>`
   - `submission_url = <url-from-cmd_submit>`
   - `competition_id`, `run_id`, `submitted_at = now()`
7. Update `agent_job_events` with the `devpost_submit` event_type.
8. The closing issue's body MUST be updated to link:
   - The approval comment
   - The resulting `submissions` row id
   - The Devpost submission URL
9. Do NOT iterate or retry. If the submission fails, halt and ask —
   this is the M12 stop-criterion the loop-prompts file calls out.

## Non-goals

- Do NOT iterate beyond one submission. A second submission inside
  M12 is out of scope (file an M12.x follow-up issue if needed).
- Do NOT add `cmd_draft` / `cmd_upload` / `cmd_delete` to
  `devpost.py`. Submit-only here.
- Do NOT change the reviewer-gate logic for `kaggle_submit` /
  `kernel_push`. Those continue to work as M9 / M10 wired them.
- Do NOT auto-resolve the human approval. The `kca decisions approve`
  step requires a human operator typing the command (or clicking
  Approve in the UI).
- Do NOT print credentials in any log, audit row, PR body, or
  closeout. Booleans / counts only.
- Do NOT scrape or write more than the one approved submission. The
  Devpost write path is rate-limited and observable.

## Acceptance criteria

- `tools/kca/devpost.py::cmd_submit` exists; `kca devpost submit
  --help` lists the expected flags.
- `kca devpost submit` with credentials absent exits non-zero with a
  clean refusal message and DOES NOT touch the network (verified by
  the audit-grep below; T008's e2e test will assert this too).
- The reviewer gate fires; `agent_reviews` + `human_decisions` rows
  exist with `target_op="devpost_submit"`.
- The closing issue carries the human "approved to submit" comment.
- Exactly ONE real `kca devpost submit` call runs; produces a
  non-empty `external_submission_id` + `submission_url`.
- `submissions` row written with `platform='devpost'`,
  `external_submission_id`, `submission_url`.
- The closing issue body has been edited to link the approval
  comment + submissions row id + submission URL.
- `agent_job_events` has exactly one event with
  `event_type='devpost_submit'`.
- Audit-grep: `grep -c '^kaggle\|^devpost' .agent/audit.jsonl` shows
  exactly one new `devpost` line for this milestone.
- `python -m pytest tests/ -q` still passes.

## Permissions

- File writes to: `tools/kca/devpost.py` (add `cmd_submit`),
  `tools/kca/kca.py` (subparser hook only).
- DB writes for `agent_reviews`, `human_decisions`,
  `agent_job_events`, `submissions`.
- Network out to `devpost.com` (or the picked platform's submission
  endpoint) is required; needs `dangerouslyDisableSandbox=true`
  per memory `reference_sandbox_network.md`.
- `kca decisions approve` requires a human operator.
- `git commit` of the new `cmd_submit` code is deferred to T009
  closeout.

## Closeout format

```
M12-T007 closeout
  cmd_submit: tools/kca/devpost.py::cmd_submit (added)
  Reviewer gate fired: YES (agent_reviews.id=<uuid>)
  Human decision: human_decisions.id=<uuid> (approved by <human>)
  Real submission: YES
    external_submission_id: <id>
    submission_url: <url>
    submissions.id: <uuid>
  Audit-grep: 1 devpost event recorded
  Closing issue updated: YES (approval comment + submissions row + URL linked)
  Acceptance: PASS | FAIL — link to closing issue
  Risks / blockers: ...
  Next: M12-T008 (e2e + smoke tests)
```

## Related issues

- Closing issue for M12 — this task's PR is the ONLY M12 PR that may
  check the "Live external submission" box in the PR template.
- `policy:approval-required` label is mandatory on T007's issue.

## Stop condition

Stop after 60 turns. If the real Devpost submit returns an error
(rate limit, rules violation, missing field), HALT — do NOT silently
retry. The fix path is: regenerate the submission pack in a follow-up
issue, re-request approval, re-run T007. Document the failure in the
closeout. If the reviewer gate fails to fire, HALT — that is the
exact regression M9 / M10 caught and M12 must catch too.
