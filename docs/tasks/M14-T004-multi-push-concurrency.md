# M14-T004: Per-competition concurrency + daily-budget enforcement + `cmd_push` credentials pre-check (issues #53, #62)

## Milestone
M14: goal-driven Kaggle workflow.

## Goal
Add, to `cmd_push` (and reconcile in `cmd_submit`), the pre-flight gating
of ADR-0020 §7, in order: (1) `KAGGLE_USERNAME`/`KAGGLE_KEY` credentials
pre-check mirroring `cmd_submit`'s envelope (issue #62); (2)
per-competition concurrency gate; (3) daily-budget gate (UTC calendar
day). No real Kaggle push in this Loop Prompt — exercise against a
fixture / fake competition row.

Assumes **M14-T000 / M14-T001 closeouts are PASS**.

## Read first
1. M14-T000 / M14-T001 closeouts.
2. `docs/adr/0020-goal-driven-kaggle-loop.md` §7 (gate order + UTC-day window + Kaggle-is-authority note).
3. Issue #53 (concurrency acceptance criteria) + Issue #62 (creds pre-check).
4. `tools/kca/kg.py::cmd_push` (M10 single-push path; `tools/kca/kg.py:201-277`).
5. `tools/kca/kg.py::cmd_submit` (existing creds envelope; `tools/kca/kg.py:145-162`).
6. `tools/kca/db.py` (T001 helpers: `count_active_pushes`, `count_today_submissions`, `get_competition_by_slug`).
7. Issue #21 (per-account pool — OUT of scope; M15+).

## Scope
1. **Credentials pre-check (issue #62).** In `cmd_push`, before the
   approval gate fires, refuse when `KAGGLE_USERNAME` or `KAGGLE_KEY` is
   absent, using the SAME error-envelope shape as `cmd_submit`
   (`{"ok": false, "error": "KAGGLE_USERNAME not set; cannot submit"-style,
   "competition": ..., "side_effect": ...}`). Verify the env keys are read
   for presence only — never printed.
2. **Concurrency gate.** Count current active kernel runs KCA owns for
   this competition (latest version per slug, status != TERMINAL/stalled
   via `count_active_pushes`); refuse cleanly when
   `competitions.max_concurrent_pushes` is reached; emit the active-runs
   list in the JSON response.
3. **Daily-budget gate.** In `cmd_push` and `cmd_submit`, count today's
   submissions (UTC calendar day via `count_today_submissions`); refuse
   past `competitions.max_daily_submissions`; report the next-window
   open time.
4. **Halt-on-Kaggle-error posture.** Document (in code + tests) that the
   gate is a courtesy guard; a Kaggle 429/400 is the hard authority and
   triggers a halt, not a retry.
5. **Verify no worker bypass.** Confirm no `src/worker/` path reaches
   `kaggle kernels push` bypassing `cmd_push`; if one exists, record it
   as a follow-up to move the gate to `ToolExecutor` (red-team
   open_disagreement 4).

## Non-goals
- No real Kaggle push (T008).
- No per-account quota pool (#21 / M15+).
- No smart-polling changes (T005).

## Acceptance criteria
- `cmd_push` refuses with the cmd_submit-shaped envelope when
  `KAGGLE_USERNAME`/`KAGGLE_KEY` is missing, BEFORE the approval gate
  (fixture-driven; assert via a credentials-stripped subprocess env).
- `cmd_push` refuses cleanly when `count_active_pushes >=
  max_concurrent_pushes` (fixture competition row), emitting `active_runs[]`.
- `cmd_push` / `cmd_submit` refuse past `max_daily_submissions` on a
  fixture spanning the UTC-midnight boundary; the count resets at UTC 00:00.
- Audit-grep: 0 lines reach `kaggle kernels push` / `kaggle competitions
  submit` from any test process.
- The bypass check is recorded in the closeout (gate stays in `cmd_push`,
  or a follow-up issue is filed).
- `ruff check .` / `ruff format --check .` clean; no pytest regressions.

## Allowed / forbidden paths
- ALLOWED: `tools/kca/kg.py` (`cmd_push`, `cmd_submit`), `tests/fixtures/**`,
  `tests/test_m14_*` (concurrency/creds fixtures if added before T009).
- FORBIDDEN: `supabase/migrations/**`; `tools/kca/db.py` schema changes;
  `tools/kca/goal.py` / `explore.py`.

## Permissions
- READ_ONLY against Kaggle for `competition_view` (limit population is
  T001's; T004 only reads the DB row).
- No real Kaggle push / submit. `git add` deferred to T009.

## Closeout format
```
M14-T004 closeout
  Creds pre-check: cmd_push mirrors cmd_submit envelope; fires before approval gate (#62)
  Concurrency gate: refuses at max_concurrent_pushes; active_runs[] emitted (#53)
  Daily-budget gate: cmd_push + cmd_submit refuse past max_daily_submissions (UTC-day window)
  Worker bypass check: <none found | follow-up #NN filed>
  Audit-grep: 0 real Kaggle lines
  pytest / ruff: <X> passed; clean
  Acceptance: PASS
  Next: M14-T005 (smart polling)
```

## Related issues
- #53 (multi-push concurrency), #62 (creds pre-check). Cross-ref #21 (deferred).

## Stop condition
Stop after 60 turns. HALT and ask if:
- A worker path reaches `kaggle kernels push` bypassing `cmd_push` —
  the gate must move to `ToolExecutor`; pause and confirm scope.
- The fixture cannot exercise the UTC-midnight reset deterministically —
  use a clock-injection seam, do not depend on wall-clock.
