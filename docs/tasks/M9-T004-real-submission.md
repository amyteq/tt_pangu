# M9-T004: ONE real Kaggle submission under explicit approval

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Run **exactly one** real `kca kaggle submit` for Spaceship Titanic,
record the resulting public LB score in the `runs` / `submissions`
table, and link the approval comment on the closing GitHub issue.

**This is the only Loop Prompt in the entire milestone that performs a
real remote write to Kaggle.** Every other M9 task is local-only.

This task assumes:
- **M9-T002 and M9-T003 closeouts are PASS.**
- The closing GitHub issue has `policy:approval-required` AND a human
  comment with the exact phrase **"approved to submit"** (case-insensitive)
  AND the issue is labelled `decision:confirmed` AND `ai:ready`.
- `KAGGLE_USERNAME` and `KAGGLE_KEY` are present in `.env`.
- `submission.csv` produced by M9-T002 still validates.

## Read first

1. M9-T002, M9-T003 closeouts and their closing issues
2. `tools/kca/kg.py::cmd_submit`
3. `.claude/settings.json` — confirm
   `Bash(kaggle competitions submit*)` and
   `Bash(python tools/kca/kca.py kaggle submit*)` are on `ask`
4. `.claude/hooks/guard_tool.py` — confirm Kaggle submission ask gate
5. `supabase/migrations/0001_init.sql` — `submissions` table layout

## Scope

1. Re-verify all pre-conditions above. If any is not met, **halt**.
2. Run
   ```
   kca kaggle submit \
     --competition spaceship-titanic \
     --file runs/spaceship-titanic/baseline-lr/submission.csv \
     --message "M9 baseline LR; cv=<value>; run=<uuid>" \
     --json
   ```
   This will be intercepted by the `ask` permission and the
   `guard_tool.py` hook — the human must approve the live call at the
   prompt.
3. Capture the Kaggle response (submission id, public score, status).
4. Write a `submissions` row linking the `run_id`, the LB `public_score`,
   and the Kaggle submission id.
5. Update the `runs` table with the LB score.
6. Update the closing GitHub issue with:
   - the Kaggle submission id;
   - the public LB score;
   - a comment that mirrors the closeout (without secrets).

## Non-goals

- Do not run a second submit, even if the first one fails.
- Do not push a kernel.
- Do not upload a dataset or model.
- Do not iterate the model within this Loop Prompt — that's M9-T005.
- Do not print `KAGGLE_USERNAME`, `KAGGLE_KEY`, or any session cookie.

## Acceptance criteria

- Exactly **one** `kaggle competitions submit` call was made in this
  task (verifiable in `.agent/audit.jsonl` — one `kaggle_submit` row).
- A `submissions` row exists with `competition_slug='spaceship-titanic'`,
  a non-null `public_score`, and `kaggle_submission_id` populated.
- `kca run list --json` shows the LB score against the baseline run.
- Closing issue has both the approval comment and the submission record.
- No secret values appear in any commit, log, audit row, or issue
  comment.

## Permissions

- `kaggle competitions submit` requires the hook `ask` prompt + a human
  approval recorded on the closing issue. Both gates must fire.
- DB write requires `dangerouslyDisableSandbox=true`.
- `git commit` and `git push` deferred to milestone closeout.

## Rollback / stop criteria

If the Kaggle submit returns ANY error (rate limit, bad CSV, rule
violation, network error), **stop immediately**. Open a follow-up issue
documenting the failure and do **not** retry inside this task. A retry
needs a fresh approval round.

## Closeout format

```
M9-T004 closeout
  Kaggle submission id: <id>
  Public LB score: <value>   submission status: <status>
  runs.public_score updated: YES   submissions.id: <uuid>
  Approval comment URL: <github-comment-url>
  Audit rows: 1 kaggle_submit (single-submission policy held)
  Secret values printed anywhere? NO  (verified by grep over logs)
  Acceptance: PASS | FAIL — link to issue
  Next: M9-T005 ready to start (local-only second experiment)
```

## Stop condition

Stop after 60 turns. **Single submission only**; if it fails, stop and
escalate. Do NOT remove safety gates "to make the submit work".
