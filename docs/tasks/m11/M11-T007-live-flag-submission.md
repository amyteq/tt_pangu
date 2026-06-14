# M11-T007: ONE real flag submission to a live CTFtime-listed event

## Milestone
M11: authorized CTF / lab workflow.

## Goal
Run exactly ONE real `kca ctf flag submit` against a live CTFtime-listed
event (e.g. `bbbctf.com` or the next-pick from the planning Q&A) under
explicit human approval. Record the resulting `ctf_attempts` row with
`accepted=true|false` and the event's HTTP status. This is the ONLY
Loop Prompt in M11 that makes a real external API call.

## Read first

1. M11-T003 closeout (`kca ctf flag submit` credential-gate)
2. M11-T006 closeout (`flag_submit` reviewer-gate round-trip)
3. `tools/kca/ctf.py::cmd_flag_submit`
4. `.claude/settings.json` — `Bash(kca ctf flag submit*)` on ask
5. `supabase/migrations/0008_m11_ctf.sql` — `ctf_attempts` shape
6. `docs/tasks/m9/M9-T004-real-submission.md` — single-submission precedent
   (Kaggle CSV submit)
7. `docs/tasks/m10/M10-T004-real-kernel-push.md` — single-push precedent
   (Kaggle kernel push)

## Pre-conditions (verify ALL before running)

- M11-T006 closeout shows a `decision:confirmed` human decision on the
  closing issue.
- `~/.ctf/<event-slug>.json` (or `CTF_<EVENT>_USERNAME` +
  `CTF_<EVENT>_TOKEN`) is populated for the chosen event (human
  action; no automation).
- A `ctf_scopes` row exists for the chosen event with `target_urls`
  covering the submit endpoint; `expires_at` is null or in the future.
- The closing issue carries `policy:approval-required` AND a human
  comment explicitly approving the submission (this milestone's only
  such record). The wording MUST match the M9-T004 / M10-T004
  precedent.
- The flag to submit was recovered LOCALLY (or via an in-scope
  `challenge_run` against the live event's challenge endpoint, also
  under approval — that approval must have its own row in
  `agent_reviews`).
- `KCA_ALLOW_REMOTE=1` AND `dangerouslyDisableSandbox=true` are set
  for the agent shell.

## Scope

1. **Register the live event** (if not already): `kca ctf event
   register --slug <slug> --name <name> --ctftime-id <n> --url
   <event-url> --credentials-ref ~/.ctf/<slug>.json`.

2. **Set the scope row** for the submit endpoint:
   `kca ctf scope set --slug live-<event-slug>
   --authorized "Live CTFtime event <slug>; one-shot flag submission"
   --target-urls "<submit-endpoint>"
   --expires-at <iso, e.g. event end_at>`.

3. **Verify scope** before submitting: `kca ctf scope verify --slug
   live-<event-slug> --url <submit-endpoint>` — must exit 0.

4. **Submit the flag.** Run exactly ONE command:
   ```bash
   kca ctf flag submit \
     --event <slug> \
     --challenge <challenge-slug> \
     --flag-file <path-to-flag-file>
   ```
   The command:
   - Fires the `flag_submit` reviewer-gate (already approved per
     T006-style round-trip, recorded on the closing issue).
   - Reads the flag from `--flag-file`. NEVER echoes the value.
   - POSTs to the event's submit endpoint.
   - Records a `ctf_attempts` row with `accepted=<bool>`,
     `http_status=<int>`, `flag_length=<int>`, `response_excerpt=<256-
     char redacted excerpt>`.

5. **Post-submit hygiene.**
   - `shred -u <path-to-flag-file>` (or `rm` with `wipe -i` if
     available) — the flag file should not survive on disk past the
     submission.
   - `git status` — confirm no `~/.ctf/*` or flag file accidentally
     staged.

6. **Record the result on the closing issue** as a comment that
   includes:
   - `ctf_attempts.id=<uuid>`
   - `accepted=<bool>`
   - `http_status=<int>`
   - The approval comment link.
   - NEVER the flag value or any credential.

## Non-goals

- Do NOT submit a second flag inside this Loop Prompt. If the human
  later wants more, that's a follow-up issue.
- Do NOT retry on error. If the event returns rate-limit / invalid-
  flag / scope-drift, HALT and file a follow-up issue.
- Do NOT echo the flag value in stdout / stderr / log / DB row / PR
  body / GitHub comment.
- Do NOT modify `tools/kca/ctf.py` here — the credential-gate +
  reviewer-gate path is already wired in T003 / T006.
- Do NOT bypass the reviewer-gate "even if the human already
  approved on the issue". The gate must still fire and write the
  `agent_reviews` row for this specific run.

## Acceptance criteria

- Exactly ONE new row in `ctf_attempts` with `submitted_at` in the
  current Loop Prompt's window and `http_status` populated.
- `accepted` is `true` OR `false` (not null). If false, the closeout
  documents the event's rejection reason (excerpted, redacted).
- One new `agent_reviews` row with `target_op='flag_submit'` and
  verdict matching the approval.
- One new `human_decisions` row linked to the review.
- Closing GitHub issue has a comment linking the approval comment +
  the `ctf_attempts.id`.
- Flag file is wiped post-submit (verify with `ls <path>` returning
  non-existent).
- Audit-grep across the entire Loop Prompt's session: 0 lines echo
  the flag value.
- `git status` clean (no `~/.ctf/*` or flag file staged).

## Permissions

- LOCAL_WRITE DB inserts via `src/db/ctf.py`.
- One real external network call to the event's submit endpoint
  (the only such call in M11).
- `dangerouslyDisableSandbox=true` + `KCA_ALLOW_REMOTE=1`.
- `shred` / `rm` on the flag file.
- No `git push` / `gh pr` activity from this Loop Prompt — milestone
  closeout (T009) handles it.

## Closeout format

```
M11-T007 closeout
  Live event: <slug> (<ctftime-id>); endpoint: <submit-endpoint>
  Scope row: live-<slug> — target_urls covers submit endpoint; expires_at=<iso>
  flag_submit reviewer-gate: agent_reviews.id=<uuid>; verdict=approve
  ctf_attempts: id=<uuid>; accepted=<bool>; http_status=<int>; flag_length=<n>
  Flag file wiped: YES (path no longer exists)
  Closing-issue comment: <url>
  Audit-grep for flag value: 0 hits across session
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T008 ready to start
```

## Related issues

- M11 proposal issue (TBD). M11-T007 closes the "single live
  submission" bullet AND must be the issue carrying
  `policy:approval-required` + `decision:confirmed`.

## Stop condition

Stop after 60 turns. If the event returns ANY error other than
`accepted=true|false`, HALT and file a follow-up issue. Do NOT retry.
If the credential file cannot be loaded, HALT and ask the human to
populate it — do NOT attempt to write it from inferred values.
If the scope-verify command does not return exit 0, HALT — do NOT
widen the scope row to make it pass; route through the human.
