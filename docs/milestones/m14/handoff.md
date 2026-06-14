# M14 → M15 Handoff Prompt

_Generated 2026-06-10 from `docs/milestones/m14/final-review.md`._

Paste this into a fresh session picking up M15 (the goal-loop submit step
and the rest of the cross-account / FK-hardening backlog) or any work that
touches the goal-driven Kaggle loop.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M14 are complete** (M11 with T007 deferred; M12 with T007 deferred;
M14 with T008's "≥ 2 LB scores" exit criterion PASS-WITH-DEVIATION). The
goal-driven Kaggle loop now exists end-to-end EXCEPT the final submit step.

## Read these files first

1. `PROJECT_STATE.md` — confirms M14 closed; M15 next.
2. `docs/milestones/README.md §M14` — completion note + the full exit-criteria list.
3. `docs/milestones/m14/final-review.md` — 24-row validation matrix + deviations.
4. `docs/adr/0020-goal-driven-kaggle-loop.md` — the loop's design, plus the
   new **"Known gaps / follow-ups"** section (push≠submit, refresh-rules).
5. `docs/evidence/m14/T008/live-run.md` — the auditable live-run record that
   surfaced every fix this milestone made.
6. `docs/adr/0019-eval-regression-suite.md` "Addendum (M14-T009)" — the
   eval-delta-check PR gate + per-suite `failure_threshold`.

## State at M14 exit

- CLI: `kca goal {init,show,update}` (`tools/kca/goal.py`),
  `kca explore {init,run,rank,prune,propose-next}` (`tools/kca/explore.py`).
- Schema: migration `0011_m14_goal_loop.sql` is **live on cloud Supabase**
  (`goals` table; `competitions.max_concurrent_pushes` / `submission_format`
  / `accelerators_allowed` / `internet_allowed` / `deadline_at` /
  `rules_summary_url`; `submissions.goal_id`; `experiment_runs.analysis_jsonb`).
- Gates: per-competition concurrency + daily-budget + `cmd_push` creds
  pre-check (matches `cmd_submit`'s envelope, #62).
- Poller: `_watch_kernel_until_terminal` (Fibonacci QUEUED / stable RUNNING /
  size-fallback terminal / QUEUED-stall release / batched `kernels list`).
- Stuck: detector fires at 3 non-improving SCORED submissions →
  `kaggle.exploration_stuck` decision + redacted escalation doc.
- Eval CI: `eval-delta-check` PR gate in `.github/workflows/eval.yml`,
  baseline `eval/baselines/mocked-baseline.json`, `eval:waive-delta` bypass.
- Tests: `tests/test_m14_*.py` — 117 with ephemeral PG / 74 + 43-SKIP in
  sandbox; 0 failures. The ephemeral fixtures are now **cloud-faithful**
  (real `run_status` enum, `submissions.project_id NOT NULL`, `agent_jobs`
  with no `competition_id`) so they no longer mask schema drift.

## M14-T009 correctness fixes (cloud-schema; all live-verified)

1. explore lifecycle writes valid `run_status` enum + `analysis_jsonb.explore_stage`.
2. `create_submission` populates NOT NULL `submissions.project_id`.
3. `create_job` matches the live `agent_jobs` schema (no `competition_id`;
   `job_type` set; linkage in `payload`).
4. `count_active_pushes` normalizes status casing (`SubmissionStatus.COMPLETE`
   → terminal).
5. (doc-only) push≠submit gap — ADR-0020 + **issue #77**.
6. `refresh-rules` degrades cleanly on kaggle 2.0.1 — `KaggleApiUnsupported`
   typed error + `{"degraded": true}` envelope; **issue #78** tracks the port.

## M15 follow-ups (do these next)

1. **#77 — explicit submit step** (the single hardest unmet M14 exit
   criterion). After a kernel push reaches terminal, submit its output CSV
   (`kaggle competitions submit` or the kernel "Submit to Competition") so
   `kca kaggle score` finds an LB row and the goal advances on real signal.
   Account for the submit in the daily-budget gate. Add a push→submit→score
   e2e test (submit mocked). Also re-mount the competition data for the
   alt-backbone kernel that errored on push #2.
2. **#78 — port `refresh-rules`** off the removed `competition_view` to the
   current Kaggle API surface; keep the graceful-degradation path.
3. **#21 — cross-account quota pooling** (deferred from M14).
4. **#60 — `approved_by_user_id` FK hardening** on `human_decisions`.
5. **Kaggle dataset / model uploads** (kernel pushes only in M14).

## Guardrails carried forward

- One live multi-push series was sanctioned for M14-T008 only; M15 live
  writes need a fresh per-batch human approval (ADR-0020 §8; grant expires
  at UTC midnight).
- Cloud DB access uses the pooler under `dangerouslyDisableSandbox=true`
  with `KCA_DB_TARGET=remote KCA_ALLOW_REMOTE=1`; never print secret values.
- No `git push --force`, no `gh pr merge` (human-only), no push to `main`.
