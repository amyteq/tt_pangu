# M14-T001: Migration 0011 (`goals` + `competitions.max_*` + `experiment_runs.analysis_jsonb`) + DB helpers

## Milestone
M14: goal-driven Kaggle workflow.

## Goal
Land the `goals` table, the new `competitions` rules/limit columns, the
`submissions.goal_id` FK, and the `experiment_runs.analysis_jsonb`
column via `supabase/migrations/0011_m14_goal_loop.sql`; the matching
helpers in `tools/kca/db.py`; and the competition-rules ingestion path
(absorbs #8 + #7). No `kca goal` / `kca explore` CLI surface yet (T002+).

Assumes **M14-T000 closeout is PASS** and the M14 proposal issue has
reached `decision:confirmed` + `ai:ready` (including the legacy-
archaeologist skip marker).

## Read first

1. M14-T000 closeout (ADR-0020 + architecture doc).
2. `docs/adr/0020-goal-driven-kaggle-loop.md` (the schema this implements).
3. `docs/architecture/goal-driven-kaggle-loop.md` (table layouts).
4. `supabase/migrations/0010_m13_eval.sql` (most recent migration; idempotency posture).
5. `supabase/migrations/0001_init.sql` (`competitions` already has `max_daily_submissions`, `metadata jsonb`).
6. `supabase/migrations/0004_m4_competition_repo.sql` (`submissions.public_lb_score`; `experiment_runs.analysis text`).
7. `tools/kca/db.py` (existing helpers: `ensure_competition`, `create_experiment_run`, `update_submission`, `update_competition`).
8. `tools/kca/competition.py` (`cmd_register` / info pattern).
9. Issue #8 (competition-rules ingestion — parent) + #7 (submission-format sub-task).

## Scope

1. **Migration `supabase/migrations/0011_m14_goal_loop.sql`** —
   idempotent (`CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`):
   - `goals` table per ADR-0020 §2 / architecture doc table layout
     (id, competition_id FK, target_lb_score, target_lb_rank,
     target_rank_kind, deadline, exit_strategy, max_total_pushes,
     stuck_threshold, status, created_at, closed_at, closed_reason).
   - Partial unique index `goals (competition_id) where status='active'`.
   - `competitions` ADD COLUMN IF NOT EXISTS: `max_concurrent_pushes int`,
     `rules_summary_url text`, `last_rules_fetch_at timestamptz`,
     `submission_format jsonb`, `accelerators_allowed text[]`,
     `internet_allowed boolean`, `deadline_at timestamptz`. (Ensure
     `max_daily_submissions` exists — it does, from 0001.)
   - `submissions` ADD COLUMN IF NOT EXISTS `goal_id uuid references
     goals(id) on delete set null`.
   - `experiment_runs` ADD COLUMN IF NOT EXISTS `analysis_jsonb jsonb`
     (nullable; leaves `analysis text` untouched — NO `text→jsonb` cast).
   - Index `submissions (goal_id) where goal_id is not null`.

2. **DB helpers in `tools/kca/db.py`** (LOCAL_WRITE pattern; gated):
   - `create_goal(competition_id, target_lb_score, target_lb_rank,
     target_rank_kind, deadline, exit_strategy, max_total_pushes,
     stuck_threshold) -> str` (refuses if an active goal exists).
   - `update_goal(goal_id, **fields)` / `close_goal(goal_id, status, reason)`.
   - `get_active_goal(competition_id) -> dict | None`.
   - `count_active_pushes(competition_id) -> int` (latest version per
     slug, status != TERMINAL/stalled — read from `submissions` +
     `experiment_runs.analysis_jsonb`).
   - `count_today_submissions(competition_id) -> int` (UTC calendar day).
   - `refresh_competition_rules(slug)` — calls `kaggle.api.competition_view`
     + best-effort parse of the public rules page; writes the new
     columns + `last_rules_fetch_at`. READ_ONLY against Kaggle (no submit/push).
   - `set_run_analysis_jsonb(run_id, **keys)` / `get_run_analysis_jsonb(run_id)`.

3. **Competition-rules ingestion (#8 / #7).**
   - Extend `tools/kca/competition.py::cmd_register` to populate the new
     columns at register time (best-effort; tolerate missing fields).
   - Add `kca competition refresh-rules --slug ...` for on-demand refresh.

## Non-goals

- No `kca goal` / `kca explore` verbs (T002 / T003).
- No real Kaggle submit / kernel push. `refresh_competition_rules` is
  READ_ONLY (`competition_view` / public page only).
- Do not modify existing migrations or cast `analysis text`.

## Acceptance criteria

- `0011_m14_goal_loop.sql` applies cleanly twice in a row against the
  cloud Supabase pooler (idempotent).
- `tools/kca/db.py` exports the helpers in scope step 2; `ruff check .` /
  `ruff format --check .` clean.
- `create_goal` refuses a second active goal for a competition
  (partial-unique-index-backed).
- `count_today_submissions` uses a UTC-day window (assert with a fixture
  spanning the UTC midnight boundary).
- `kca competition refresh-rules --slug tpu-getting-started --json`
  writes the new columns (READ_ONLY; assert 0 lines reach `kaggle
  competitions submit` / `kaggle kernels push`).
- No regressions in `pytest tests/ services/decision_api/tests`.

## Allowed / forbidden paths

- ALLOWED: `supabase/migrations/0011_m14_goal_loop.sql`, `tools/kca/db.py`,
  `tools/kca/competition.py`, `tests/test_m14_*` (only if adding a
  migration smoke; the formal suite is T009).
- FORBIDDEN: existing migrations `0001`–`0010`; `tools/kca/kg.py`;
  `src/worker/**`; any `kca goal`/`kca explore` surface.

## Permissions

- LOCAL_WRITE (cloud Supabase pooler) — applies new migration; ALLOWED;
  needs `dangerouslyDisableSandbox=true` (pooler is off-sandbox).
- Kaggle `competition_view` (READ_ONLY) — ALLOWED for `refresh-rules`.
- No real Kaggle submit / push. `git add` deferred to T009.

## Closeout format

```
M14-T001 closeout
  Migration: supabase/migrations/0011_m14_goal_loop.sql (applied; idempotent verified)
  DB helpers: tools/kca/db.py +<n> (create_goal, update_goal, close_goal, get_active_goal, count_active_pushes, count_today_submissions, refresh_competition_rules, set/get_run_analysis_jsonb)
  Rules ingestion: cmd_register populates new cols; `kca competition refresh-rules` added
  analysis_jsonb: added as new nullable column; analysis text untouched (verified)
  pytest: <X> passed / <Y> skipped (0 regressions)
  ruff: clean
  Acceptance: PASS
  Next: M14-T002 (kca goal CLI + goal.md)
```

## Related issues
- #8 (competition-rules ingestion — parent), #7 (submission-format sub-task).

## Stop condition
Stop after 60 turns. HALT and ask if:
- The migration cannot apply idempotently.
- A helper name collides with an existing `tools/kca/db.py` function.
- `refresh_competition_rules` cannot populate columns without a real
  submit/push (it must not — READ_ONLY only).
