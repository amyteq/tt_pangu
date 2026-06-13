# M14-T008 — live end-to-end goal-driven Kaggle run (evidence)

_Branch: `worktree-m14-goal-loop`. Competition: `tpu-getting-started`
(id `1e6b3286-00b5-4e86-83ad-3bc94596e0a4`). Date: 2026-06-10 (UTC)._

This is the auditable record of the ONE live multi-push series sanctioned
for M14. All other M14 tasks are offline. Secrets (DSN password,
`KAGGLE_KEY`) never appear here.

## Human approval (per-batch budget grant)

Operator Harry (harry@ayla-app.com) explicitly chose **"Approve live run
now"** over dry-run/defer in-session. Recorded as:

- `human_decisions.id = 8552dcfb-c60b-4bd7-a076-77dd3aefbb5a` —
  `decision_type = kaggle.kernel_push`, `status = approved`,
  `selected = "Approve live run now"`.
- `agent_reviews.id = b389a993-fc20-4ac5-9619-eeb9da6f2a4b` —
  `verdict = approve`, `target_op = kaggle.kernel_push`,
  `decision_id = 8552dcfb-…`.
- `agent_jobs.id = 1d39395e-37c4-47b2-b3ae-a06bc41b44ae` —
  `job_type = kaggle.push.series`.

ADR-0020 §8: the grant expires at UTC midnight.

## Competition rules set

`kca competition refresh-rules` is unavailable on the installed kaggle CLI
(2.0.1: `'KaggleApi' object has no attribute 'competition_view'`), so the
real Kaggle limits could not be auto-ingested. Per the T008 instruction the
safe small bound was applied via a direct DB update:

- `competitions.max_concurrent_pushes = 2`
- `competitions.max_daily_submissions = 5`

## Goal

`kca goal init --competition tpu-getting-started --target-lb-score 0.85
--target-lb-rank 30 --target-rank-kind percentile --exit-strategy
first_reached`

- `goals.id = 4c19e7bb-3cad-4775-b9e6-074ecd83b0db`
- target: public LB ≥ 0.85 OR rank top-30% (first_reached);
  `max_total_pushes = 20`, `stuck_threshold = 3`.
- `experiments/tpu-getting-started/goal.md` written (mirror).

## Candidate batch (seeded from existing M10 artifacts)

The real local trainer was deliberately not built (T003 `kca explore run`
without `--dry-run` raises `NotImplementedError`), so per the T008 sanction
the candidate batch = the two existing push-ready M10 artifacts. Ingested
directly (no live local screening — M10 local-slice holdout used):

- `experiment` (batch carrier) id `4cbf2bbb-1012-4c1f-b45a-c8cc1076f27b`,
  `analysis_jsonb.exploration_batch_id = a3e685cf-66b8-446b-8fc1-74896174c92a`.
- run `7207c762-933e-47d6-b53a-229e44200f77` — `baseline-tl`
  (MobileNetV2, 192px, 3ep, TPU), M10 holdout 0.4310.
- run `0bf8b5b6-604c-486c-ba29-0586b26de96e` — `alt-backbone-v1`
  (EfficientNetB0, 192px, 3ep, GPU), M10 holdout 0.3966.

## Concurrency gate (T004) — verified firing

With one stale M10 submission row counted active and one fresh candidate-1
row, `count_active_pushes = 2 = max_concurrent_pushes`. An attempted push of
candidate 2 was **refused before any Kaggle call**:

```
{"ok": false, "error": "max_concurrent_pushes reached (2/2); refusing to push",
 "active_pushes": 2, "max_concurrent_pushes": 2, ...}
```

The pre-existing M10 row carried status `SubmissionStatus.COMPLETE`, which
is not the lowercase `complete` token in `db._PUSH_TERMINAL_STATUSES`, so it
was mis-counted as active. It was normalized to `complete` (the run is in
fact complete) to free the slot, then the series proceeded one push at a
time. See "Findings" below.

## Live pushes (REAL `kaggle kernels push`, auto-watched by T005)

| # | kernel ref | version | push | watch terminal | polls | queue_s | running_s | kernel result |
|---|---|---|---|---|---|---|---|---|
| 1 | harrysun2006/petals-baseline-tl | 6 | OK (200) | yes | 3 | 1.8 | 605.3 | ran clean, no error excerpt |
| 2 | harrysun2006/petals-alt-backbone-efficientnetb0 | 1 | OK (200) | yes | 2 | 3.0 | 301.0 | ran to terminal but **errored** in-notebook |

Push #2 kernel error (extracted by the T005 poller, not a Kaggle API error):

```
RuntimeError: No data source resolved: not on Kaggle (GCS/input path
absent) and no local slice present.
```

Cause: `alt-backbone-v1/kernel-metadata.json` has `enable_internet: false`
and `enable_gpu: true`; the notebook's data-source resolution failed in the
Kaggle GPU runtime. This is a candidate runtime failure, **not** a push /
4xx / 5xx / rate-limit / rules error, so the T008 HARD-HALT rule did not
fire. No retry was attempted.

No Kaggle 429/400 occurred on either push. `max_daily_submissions = 5` and
`max_total_pushes = 20` were honoured (2 pushes used).

## Scores (`kca kaggle score`)

`kca kaggle score --competition tpu-getting-started --kernel-ref
petals-baseline-tl` and `…petals-alt-backbone-efficientnetb0` both returned
`match_count: 0`. **A kernel push + run does not create a competition
leaderboard submission** — that needs an explicit submit of the output CSV.
Therefore neither T008 push produced a new `public_lb_score`.

The only scored submission for this competition remains the M10 v5 push:
`public_score = 0.76505` (Kaggle ref 53482431, dated 2026-06-08). That row
(`submissions.id = 107f97f9-e9a4-45a1-b872-5806cca08c82`,
`public_lb_score = 0.765050`) was linked to this goal as best-known LB.

## Submissions linked to the goal

| submissions.id | file_path (kernel slug) | status | public_lb_score |
|---|---|---|---|
| 107f97f9-e9a4-45a1-b872-5806cca08c82 | (M10 csv) | complete | 0.765050 |
| e1c89b6e-694f-4f77-a433-f6f1536626b9 | harrysun2006/petals-baseline-tl | complete | NULL (kernel ran, not submitted) |
| 75980ea8-7fdf-4fe0-a073-434636322fe1 | harrysun2006/petals-alt-backbone-efficientnetb0 | error | NULL (kernel errored) |

## Goal evaluation

- Best LB linked to goal: **0.765050** (M10 carry-over).
- `goal_remaining_delta = 0.08495` (target 0.85 − 0.765050).
- **Goal NOT reached.**
- No further iteration: this is a single 2-candidate batch and the real
  trainer is unbuilt, so `propose-next` + a real local screen + new training
  would be required to improve — out of T008 scope. The T007 stuck detector
  was NOT fired (no fabricated escalation churn).

## Findings (route back to owning tasks — no source edits in T008)

1. **Submission-status normalization (M10 / T004 data).** A
   `SubmissionStatus.COMPLETE` string is not matched by
   `db._PUSH_TERMINAL_STATUSES` (lowercase `complete`), so a finished run is
   mis-counted as an active concurrency slot. Normalize submission status on
   write, or lowercase/strip the enum prefix in `_count_active_pushes`.
2. **`run_status` enum lacks `planned`/`screened`.** T003's
   `_set_run_status(run_db_id, "planned"/"screened")` writes values not in
   the DB `run_status` enum (`queued/running/succeeded/failed/cancelled`) —
   it raises `InvalidTextRepresentation` against the real schema. Either add
   the enum values in a migration or store the batch lifecycle state in
   `analysis_jsonb` instead of the enum column.
3. **`db.create_submission` / `db.create_job` schema drift.**
   `create_submission` omits the NOT-NULL `submissions.project_id`;
   `create_job` references a non-existent `agent_jobs.competition_id`. Both
   need to match the live cloud schema.
4. **Kernel push ≠ leaderboard submission.** The goal loop assumes a push
   yields a scorable submission; for a competition kernel it does not. T008
   surfaced that the loop needs an explicit submit step (or kernel
   "Submit to Competition") before `kca kaggle score` can find a row.
5. **`alt-backbone-v1` kernel metadata.** `enable_internet: false` +
   missing data mount → in-notebook `RuntimeError`. The kernel needs the
   competition data source mounted / internet enabled to run on Kaggle.
6. **`kca competition refresh-rules`** is broken on kaggle CLI 2.0.1
   (`competition_view` removed). Needs the current API surface.
