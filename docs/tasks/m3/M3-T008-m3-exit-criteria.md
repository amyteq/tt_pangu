# M3-T008: M3 exit criteria validation

## Milestone
M3: Python-first competition worker v0.

## Goal
Confirm all M3 exit criteria are met. Produce a `docs/milestones/m3/final-review.md` summary
analogous to `docs/milestones/m2/final-review.md`.

## Read first
1. `docs/milestones/README.md` — M3 exit criteria
2. `docs/milestones/m2/final-review.md` — template for final review format
3. All `docs/tasks/m3/M3-T*.md` specs
4. `supabase/migrations/0003_m3_worker.sql`
5. `src/worker/worker.py`, `src/worker/tools.py`, `src/worker/budget.py`
6. `scripts/run_job.py`
7. `tests/test_worker_smoke.py`

## Validation matrix

Run each check. Report PASS / FAIL / SKIP (skip only if DB unavailable):

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | Migration 0003 idempotent | `cat supabase/migrations/0003_m3_worker.sql \| psql $SUPABASE_DB_URL -v ON_ERROR_STOP=1` (twice) | 0 errors both times |
| 2 | `agent_job_events` table exists | `psql $SUPABASE_DB_URL -c "\d agent_job_events"` | columns listed |
| 3 | `agent_jobs` has new columns | `psql ... -c "\d agent_jobs" \| grep -E "workspace_path\|turns_used\|cost_usd\|policy"` | 4 lines |
| 4 | Import rename clean | `grep -r "from \. import kaggle\|import tools.kca.kaggle" tools/ tests/` | empty |
| 5 | Full test suite | `python -m pytest tests/ -v` | 0 failed |
| 6 | Worker dry run — done | `python scripts/run_job.py --prompt "test" --max-turns 5 --dry-run --json` | exit 0; status=done |
| 7 | Worker dry run — budget stop | inline python with max_turns=1 and infinite_tool scenario | status=budget_stop |
| 8 | Workspace lifecycle | init → list → clean → `git worktree list` | worktree removed |
| 9 | kca decisions list | `python tools/kca/kca.py decisions list --pending --json` | exit 0, valid JSON |
| 10 | Kaggle submit still blocked | `KCA_ALLOW_REMOTE= python tools/kca/kca.py kaggle submit ...` | exit 2 |
| 11 | M3 exit criterion A | `python scripts/run_job.py --prompt "Read CLAUDE.md and summarize" --max-turns 5 --dry-run --json` | status=done, turns_used≥1 |
| 12 | M3 exit criterion B | Check `turns_used`, `cost_usd` in result | both > 0 |
| 13 | No remote side effect | grep for `kaggle.api` / real `kaggle` CLI calls in `src/worker/` | none |
| 14 | Worker smoke tests | `python -m pytest tests/test_worker_smoke.py -v` | 6/6 passed |

## Required output: `docs/milestones/m3/final-review.md`

Use the same structure as `docs/milestones/m2/final-review.md`:

- Date, branch
- Milestone exit criteria (from milestones.md) — status: met / partially met / not met
- Validation matrix (filled in from above checks)
- Files added or changed (path + one-line summary)
- Behaviour added (3–5 bullet points)
- Risks (known gaps, sharp edges, follow-ups)
- Approval needs (none expected)
- M4 follow-ups

## M4 follow-up stubs to include

The following items should appear in the M4 follow-ups section of the review:
1. **Resume after approval**: re-run paused job with granted decision.
2. **Real `kkr.py` wiring**: connect `kca kaggle push/submit` to the legacy script.
3. **CI job**: GitHub Actions step that runs DB smoke + worker smoke suites.
4. **Model routing**: route by task difficulty (Sonnet default, Opus for hard tasks).
5. **Kaggle data download**: `kca kaggle data download --competition <slug>` wrapper.
6. **Competition context loading**: worker receives competition rules + metric in its system prompt.

## Acceptance criteria
- Validation matrix has 0 FAIL rows (SKIP for DB checks without `SUPABASE_DB_URL` is acceptable).
- `docs/milestones/m3/final-review.md` exists and follows the template.
- "M3 EXIT CRITERIA MET" appears in the review doc.

## Stop condition
Stop after 30 turns. If any check produces a FAIL that is not trivially fixable within
5 turns, document the FAIL with the exact output and propose a patch — do not loop
indefinitely trying to fix it.
