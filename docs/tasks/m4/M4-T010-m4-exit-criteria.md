# M4-T010: M4 exit criteria validation

## Milestone
M4: Kaggle competition workflow v0.

## Goal
Confirm all M4 exit criteria are met. Produce `docs/milestones/m4/final-review.md`.

## Read first
1. `docs/milestones/README.md` — M4 exit criteria
2. `docs/milestones/m3/final-review.md` — template
3. All `docs/tasks/m4/M4-T*.md` specs
4. `supabase/migrations/0004_m4_competition_repo.sql`
5. `tools/kca/competition.py`, `tools/kca/kg.py`, `tools/kca/workspace.py`
6. `scripts/run_job.py`
7. `tests/test_m4_smoke.py`

## Validation matrix

Run each check. Report PASS / FAIL / SKIP:

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | Migration 0004 idempotent | apply twice via psql | 0 errors |
| 2 | `competitions` has repo columns | `\d competitions` | `repo_url`, `default_branch`, `local_clone_path` |
| 3 | `experiments` table exists | `\dt` | present |
| 4 | `experiment_runs` table exists | `\dt` | present |
| 5 | `submissions` table exists | `\dt` | present |
| 6 | `kca --help` on PATH | `pip install -e . && kca --help` | subcommand list shown |
| 7 | `kca competition list --json` | no DB | exit 0, `{"ok": ..., "competitions": []}` |
| 8 | `kca competition register --slug test --json` | with DB | exit 0, slug recorded |
| 9 | `kca workspace init --repo <local_repo> --json` | bare git repo | worktree created |
| 10 | `kca run init --competition titanic --json` | any dir | meta.json created |
| 11 | `kca run record-metric --key cv_accuracy --value 0.82 --json` | run dir from #10 | metrics.json updated |
| 12 | `kca kaggle push --dry-run --json` | no credentials | exit 0, dry_run=true |
| 13 | `kca kaggle submit` without credentials | no `KAGGLE_KEY` | exit non-zero, clear error |
| 14 | Approval gate default=allow | policy.kaggle_submit=False | submit NOT blocked |
| 15 | Approval gate override=require | policy.kaggle_submit=True | ApprovalRequired raised |
| 16 | Full test suite | `python -m pytest tests/ -v` | 0 failed |
| 17 | TC-1 Titanic dry-run | run_job.py dry-run loop | all 7 validation checks pass |
| 18 | M4 exit criterion A | Competition runs in own repo | competition repo worktree used |
| 19 | M4 exit criterion B | TC-1 produces submission.csv | 418 rows, valid format |
| 20 | M4 exit criterion C | Submission validated locally; no unapproved Kaggle call | decisions list empty |

## Required output: `docs/milestones/m4/final-review.md`

Structure:
- Date, branch
- M4 exit criteria (from milestones.md): met / partially met / not met
- Validation matrix (filled in)
- Files added or changed
- Capabilities added
- Known gaps and risks
- M5 follow-ups

## M5 follow-up stubs

1. **Browser/research loop**: Playwright-based research job for reading competition pages.
2. **Kaggle data auto-download**: `kca kaggle download` wired to `cmd_download` + checksum validation.
3. **CI GitHub Actions**: DB smoke + worker smoke + M4 smoke on every PR.
4. **Resume paused jobs**: re-run after `kca decisions approve` (currently M4+ follow-up).
5. **Model routing**: Sonnet for implement/experiment, Opus for final eval/analysis.
6. **TC-2 House Prices**: feature engineering iteration loop.

## Acceptance criteria
- Validation matrix: 0 FAIL rows (SKIP for DB checks without `SUPABASE_DB_URL`).
- `docs/milestones/m4/final-review.md` exists and follows the template.
- "M4 EXIT CRITERIA MET" appears in the review doc.

## Stop condition
Stop after 30 turns. If any validation check is a FAIL that is not fixable within
5 turns, document the FAIL with exact output and propose a patch. Do not loop
indefinitely.
