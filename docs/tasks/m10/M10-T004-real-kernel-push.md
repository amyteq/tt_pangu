# M10-T004: ONE real Kaggle kernel push for `tpu-getting-started`

## Milestone
M10: live end-to-end regression test — Petals to the Metal.

## Goal
Execute exactly ONE real `kca kaggle push` for Petals to the Metal,
wait for the resulting kernel run on Kaggle's infrastructure to
complete, and record the public LB score in the `submissions` table.

This is the **only** Loop Prompt in M10 that runs a real Kaggle write
command. M10-T005 is local-only; a second real push in M10 is out of
scope.

## Read first

1. M10-T002, M10-T003 closeouts
2. `tools/kca/kg.py::cmd_push`
3. `.claude/settings.json` — `Bash(kaggle kernels push*)` and
   `Bash(kaggle kernels status*)` are on `ask`
4. `supabase/migrations/0001_init.sql` (`submissions` table)
5. `docs/tasks/m9/M9-T004-real-submission.md` (the CSV-submit precedent)
6. `docs/milestones/m9/final-review.md` AC #14–#16 (LB recording shape; note the
   M9-T004 workaround for migration 0004 — see issue #17)

## Pre-flight checks (HARD STOP if any fail)

Before issuing the real push, verify:

1. `runs/tpu-getting-started/baseline-tl/baseline.ipynb` still exists
   and executes locally (re-run M10-T002's local sanity end-to-end
   evidence; do not re-train, just verify the kernel-startup cells
   import cleanly).
2. `runs/tpu-getting-started/baseline-tl/kernel-metadata.json` parses
   and contains the required keys (`id`, `title`, `code_file`,
   `language`, `kernel_type`, `competition_sources`).
3. `kaggle.api.config_values` is populated (booleans only — never
   print). Equivalent: `python -c "from dotenv import load_dotenv;
   import os; load_dotenv(); print(bool(os.environ.get('KAGGLE_USERNAME')),
   bool(os.environ.get('KAGGLE_KEY')))"` prints `True True`.
4. Daily kernel-push limit not exhausted: `kaggle kernels list
   --user <kaggle-username> --csv` shows < the per-day cap. If at
   limit, halt and ask.
5. M10-T003 closing issue has `policy:approval-required` AND a human
   comment explicitly approving the push (this milestone's only such
   record). If absent, halt and ask — do not push.

## Scope

1. Run **exactly ONE** real push:
   ```
   kca kaggle push \
     --competition tpu-getting-started \
     --notebook runs/tpu-getting-started/baseline-tl/baseline.ipynb \
     --message "M10-T004 baseline-tl (transfer learning, <backbone>, image_size=<size>)" \
     --json
   ```
   Capture stdout / stderr. Expect a kernel-version reference back
   from Kaggle.
2. Poll `kaggle kernels status <kernel-ref>` (every 30s, cap at 15
   minutes for "Getting Started" competition kernels — the spec
   allows up to 60 minutes, but Petals' "Getting Started" notebooks
   typically complete in < 15). Capture the status transitions:
   `queued → running → complete` (or `error`).
3. If the kernel run errors: capture the Kaggle-side log excerpt
   (without leaking credentials) and HALT. Do NOT retry. Fail the
   milestone and open a follow-up issue per M9 rollback policy.
4. Once the kernel run is complete: fetch the resulting submission's
   public LB score via `kaggle competitions submissions -c
   tpu-getting-started`. The kernel run will have created a
   submission row server-side; capture its `external_submission_id`
   and `publicScore`.
5. Record locally:
   - `submissions` row with `competition_id=<…>`,
     `experiment_run_id=<M10-T002 row>`, `platform="kaggle"`,
     `external_submission_id=<from kaggle>`, `public_score=<lb>`,
     `status="submitted"`, `notes=` short message including kernel-
     version ref.
   - If migration 0004's optional columns are present (issue #17 has
     landed): write to the canonical `public_lb_score` / `run_id` /
     `file_path` columns instead of the M9-T004 mirror workaround.
     Otherwise mirror the LB to `experiment_runs.analysis` as
     M9-T004 did, and link to #17 in the closeout.
6. Confirm no `kaggle competitions submit`, no `kaggle datasets
   create`, and exactly one `kaggle kernels push` was issued (audit-
   grep `.agent/audit/tool-events.jsonl`).

## Non-goals

- Do not retry on error.
- Do not iterate on the notebook between push attempts (there's only
  one attempt).
- Do not push a second kernel version.
- Do not call any other Kaggle write op.

## Acceptance criteria

- Exactly one `kaggle kernels push` call. Verified via
  `kaggle kernels list --user <kaggle-username>` returning exactly +1
  new entry for this competition vs. the pre-T004 baseline, AND audit-
  grep clean (1 line begins with `kaggle kernels push`).
- The kernel run completes with status `complete` (not `error`).
- `submissions` row written with non-null `public_score` and populated
  `external_submission_id`.
- The M10-T002 `experiment_run_id` is linked to the new `submissions`
  row.
- Audit / logs / commits / issues contain NO credential values.
- All baseline validation still passes (pytest, ruff, pnpm where
  available).
- M10-T004 closing issue has the approval comment + the new
  `submissions.id` referenced.

## Permissions

- Network out to `kaggle.com` / `*.kaggle.com` is allowed; the call
  needs `dangerouslyDisableSandbox=true` for egress on this host.
- `git commit` and `git push` deferred to milestone closeout.
- Human approval recorded on the closing issue is the load-bearing
  evidence; the agent must NOT skip this check.

## Closeout format

```
M10-T004 closeout
  Kaggle kernel ref: <user>/<slug>/<version>
  Kernel run status: complete   wall time: <mm:ss>
  Public LB score: <0.xxxx>   external submission id: <id>
  submissions.id: <uuid>
  experiment_run_id linkage: <M10-T002 run id> via submissions.experiment_run_id
  Migration 0004 canonical columns used? <YES | NO — workaround mirroring to experiment_runs.analysis (see issue #17)>
  Approval comment URL: <link to the human comment on the closing issue>
  Audit rows: 1 kernel_push (single-push policy held)
  Secret values printed anywhere? NO (verified by grep over audit and captured subprocess stdout)
  Acceptance: PASS | FAIL — link to issue
  Next: M10-T005 ready to start (local-only second experiment)
```

## Related issues

- #12 — M10 proposal
- #11 — dotenv leak. NOT a pre-req for T004 (T007 is the test that
  references #11). But: if the leak still exists locally, kca kaggle
  push will work correctly because the agent intends to authenticate
  here — note this in the closeout for traceability.
- #17 — migration 0004 optional `submissions` columns. If closed
  before T004 runs, use the canonical columns; otherwise mirror as
  M9-T004 did.

## Stop condition

Stop after 60 turns. HALT if any pre-flight check fails. HALT if the
kernel run returns `error`. HALT if Kaggle returns a rate-limit or
rules-violation error. The fix path is local: regenerate the notebook
and re-request approval; do NOT silently retry within this prompt.
