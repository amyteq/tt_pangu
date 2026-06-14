# M4 / MVP-4 — final integration review

_Branch: `main`._

## Milestone exit (per docs/milestones/README.md)

> Each Kaggle competition runs in its own competition repo with experiment
> branches. The agent can register a competition, clone its repo, drive a
> per-job worktree, record runs and metrics, gate remote operations through
> a configurable approval policy, and complete the TC-1 Titanic loop
> end-to-end without a real Kaggle submission.

**Status: met.**

## Validation matrix

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | Migration 0004 idempotent (re-apply twice, `ON_ERROR_STOP=1`) | PASS | Verified against local Supabase (`127.0.0.1:54322`); both applications exit 0 with only `NOTICE` lines |
| 2 | `competitions.repo_url / default_branch / local_clone_path / competition_policy` columns added | PASS | `psql \d competitions` shows all four |
| 3 | `experiments / experiment_runs / submissions` tables exist | PASS | `psql \dt` confirms all three (existing M1 tables extended with M4 columns) |
| 4 | `kca` available on PATH after `pip install -e .` | PASS | `kca --help` lists `competition / workspace / run / nb / kaggle` |
| 5 | `kca competition list` exits 0 without DB | PASS | Returns `{"ok": true, "competitions": []}` |
| 6 | `kca workspace init --repo` creates worktree at `<repo>/jobs/<job_id>` | PASS | Verified against a temp bare git repo |
| 7 | `kca run init` creates `meta.json` | PASS | Without DB it still writes the FS layout |
| 8 | `kca run record-metric` writes `metrics.json` | PASS | `cv_accuracy=0.80` round-trips |
| 9 | Default policy: `kaggle_submit` allowed (False) | PASS | `JobPolicy.approval_gates['kaggle_submit'] == False` |
| 10 | Policy gate blocks when `kaggle_submit=True` | PASS | `_check_approval_gate` raises `ApprovalRequired` |
| 11 | `kca kaggle push --dry-run` without credentials | PASS | Validates `kernel-metadata.json` without uploading |
| 12 | TC-1 Titanic: 8/8 validation checks | PASS | meta + metrics + 419-row submission + analysis + cv 0.7912 |
| 13 | Full test suite (no DB) | PASS | 20 passed, 7 skipped, 0 failed |
| 13b | Full test suite (live DB) | PASS | 27 passed, 0 skipped, 0 failed |
| 14 | Competition repo worktree at `<repo>/jobs/<job_id>` | PASS | Same as check 6 |
| 15 | `submission.csv` validated locally; no unapproved Kaggle call | PASS | 418 rows, 0/1 only, no pending decisions |
| 16 | M4 live DB smoke: `create_experiment → create_run → record_metric → get_experiment / list_runs` round-trips | PASS | `metrics = {'cv_accuracy': 0.82}` returned by `list_runs(experiment_id=...)` |

## Files added or changed

| Path | Change |
|---|---|
| `pyproject.toml` | + `[build-system]`, `[project]`, `[project.scripts] kca`, `[tool.setuptools.packages.find]` |
| `tools/__init__.py`, `tools/kca/__init__.py` | new — empty, make the editable install discover the package |
| `supabase/migrations/0004_m4_competition_repo.sql` | new — adds `repo_url / default_branch / local_clone_path / competition_policy` to `competitions`, plus `experiments / experiment_runs / submissions` tables with indexes + RLS |
| `tools/kca/db.py` | + M4 functions (`get_competition_by_slug`, `update_competition`, `list_competitions`, `create_experiment`, `get_experiment`, `list_experiments`, `create_run`, `update_run`, `record_metric`, `list_runs`, `create_submission`, `update_submission`); renamed M2 functions to `*_m2` to avoid signature collision |
| `tools/kca/competition.py` | new — `kca competition register/clone/list/info` |
| `tools/kca/kca.py` | + register `competition` subparser |
| `tools/kca/workspace.py` | + `--repo` flag; worktree path `<repo>/jobs/<job_id>` when given |
| `tools/kca/run.py` | rewritten to be FS-first; DB writes degrade to warnings when `SUPABASE_DB_URL` absent |
| `tools/kca/kg.py` | + `ApprovalRequired` + `_check_approval_gate(operation, policy)` + `OPERATION_DEFAULTS`; `submit/push/download/upload/watch` call real `kaggle` CLI (push has `--dry-run`); credentials checked up-front |
| `src/worker/_types.py` | extended `JobPolicy.approval_gates` with the 7 ADR-0006 ops |
| `scripts/run_job.py` | + `--competition-slug`, `--branch`, `--hypothesis`, `--require-approval`; `_resolve_policy()` merges project → competition → CLI; `_resolve_competition_repo()` clones repo if needed; `_workspace_init_repo()` uses `<repo>/jobs/<job_id>`; commits agent changes on success |
| `tests/test_m4_smoke.py` | new — 10 tests, no DB / Kaggle / API |
| `tests/test_kca_smoke.py` | updated 2 tests to M4 semantics (`--dry-run` replaces stub; missing Kaggle creds surface) |
| `tests/fixtures/sample_kernel/` | new — minimal `kernel-metadata.json` + `test.py` |
| `docs/testing/job-prompts/{research,implement,prepare-submission}-titanic.txt` | new — TC-1 job prompt templates |
| `docs/milestones/m4/final-review.md` | new (this file) |

## TC-1 Titanic loop summary

- Competition repo: `/tmp/claude-1000/m4test/kaggle-titanic` (init + .gitignore + README committed).
- Baseline: `src/titanic/baseline.py` — sklearn LogisticRegression, 5-fold KFold, seaborn-built-in dataset (no Kaggle download), prints metric JSON, writes 418-row `submission.csv`.
- Run lifecycle: `kca run init` → `kca run record-metric` → `analysis.md`.
- Reported metric: `cv_accuracy = 0.7912` (well above the 0.70 sanity floor).
- No real Kaggle submission was made; `kca kaggle submit` is policy-gated and the test loop never invoked it.

## Approval gate model (ADR-0006)

`JobPolicy.approval_gates` defaults:

| Operation | Default `requires_approval` |
|---|---|
| `kaggle_submit` | False (allow) |
| `kernel_push` | False |
| `dataset_upload` | True |
| `git_push` | False |
| `git_force_push` | True |
| `supabase_migrate` | True |
| `delete_artifact` | True |

Resolution order (lowest to highest, last-write wins, **except** competition tightening is only allowed for True):

1. `JobPolicy` defaults
2. Project row's `approval_gates`
3. Competition row's `competition_policy.approval_gates` (can only flip False→True)
4. CLI `--require-approval <op1> <op2> …`

`KCA_ALLOW_REMOTE=1` remains an emergency override that suppresses the gate.

## Skipped / deferred

- Real Kaggle API calls were not exercised; `--dry-run` exercises the credential and metadata paths.
- The live-DB run used the local Supabase stack (`make supabase-up`, port 54322, password `postgres`), not the originally suggested `localhost:5432`/`s3cr3t` DSN — nothing was listening on the suggested port; the stack was the closest available DB.

## Notes on schema coexistence

Migration 0004 was rewritten as additive ALTERs against the M1 `experiments / experiment_runs / submissions` tables rather than fresh `CREATE TABLE` statements, because `CREATE TABLE IF NOT EXISTS` would silently keep the M1 schema and then fail when creating indexes on M4-only columns. The chosen path:

- Keeps every M1/M2 NOT NULL column intact.
- Adds M4 columns as nullable so re-applying the migration on a populated DB is safe.
- Makes `db.create_experiment` (M4) populate the legacy M1 `project_id` + `name` columns from the competition row + `branch`/`hypothesis`, so a single row satisfies both shapes.

The `experiment_run_metrics` event-log table (from 0002) is untouched and the M2 `record_metric_m2` flow still writes both the event row and the M2-nested jsonb snapshot. `record_metric` (M4) writes a flat `key→value` jsonb merge on `experiment_runs.metrics` and `runs/<comp>/<run_id>/metrics.json` is the flat shape mandated by Prompt 4.

## M5 follow-ups

1. **Browser/research loop** — wire Playwright MCP for reading competition rule pages, leaderboard pages, and discussion threads. Treat fetched HTML as untrusted data per CLAUDE.md operating principles.
2. **Kaggle data auto-download** — `kca kaggle download` is implemented but unverified end-to-end; add checksum validation against a manifest and resume support.
3. **CI GitHub Actions** — run DB-up + DB smoke + worker smoke + M4 smoke on every PR; gate merges on the same `pytest tests/` we run locally.
4. **Resume paused jobs** — after `kca decisions approve`, allow `scripts/run_job.py --job-id <uuid>` to pick up at the prior turn boundary instead of starting over.
5. **Model routing** — use Sonnet for implement/experiment jobs; reserve Opus for evaluation/analysis where reasoning depth matters more than throughput.
6. **TC-2 House Prices** — second test case exercising the feature-engineering iteration loop (regression metric, more complex pre-processing).
