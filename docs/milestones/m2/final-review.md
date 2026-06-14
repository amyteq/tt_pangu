# M2 / MVP-2 — final integration review

_Date: 2026-05-18.  Branch: `main`._

## Milestone exit (per docs/milestones/README.md)

> Schema and data model support MVP-1 artifacts and future worker jobs.
> A local/dev worker can record run events without needing product UI.

**Status: met.**

## Validation matrix

| # | Check | Result |
|---|---|---|
| 1 | Migration 0002 applies cleanly on fresh postgres:15 | PASS |
| 2 | Migration 0002 idempotent (re-applies with no error) | PASS |
| 3 | M1 smoke tests (`tests/test_kca_smoke.py`) | 6/6 PASS |
| 4 | M2 DB smoke tests (`tests/test_kca_db_smoke.py`) | 5/5 PASS |
| 5 | `kca run init` writes DB row + FS cache | PASS |
| 6 | `kca run record-metric` writes event + jsonb snapshot + refreshes metrics.json | PASS |
| 7 | `kca run list` reads from DB join | PASS |
| 8 | `kca run init` with DB unreachable → exit non-zero, no FS state | PASS |
| 9 | `kca kaggle submit` blocked w/o `KCA_ALLOW_REMOTE=1` | PASS (exit 2) |
| 10 | Blocked submit records `pending` `human_decisions` row when DB up | PASS |
| 11 | M1 smoke does NOT leak DB state (env-scoped) | PASS (0 leaked rows) |
| 12 | ADR-0008 present + linked from `design-decisions.md` | PASS |
| 13 | `local-supabase.md` + `m2-schema-changes.md` present | PASS |
| 14 | settings.json deny list still blocks direct kaggle CLI | PASS |
| 15 | No `.env`/`kaggle.json`/`ssh`/`aws` paths read in kca code | PASS |
| 16 | No subprocess invocations of real `kaggle` CLI in kca code | PASS |

## Files added or changed

| Path | Change |
|---|---|
| `supabase/migrations/0002_kca_run_alignment.sql` | new — adds `external_run_id`, `run_dir`, `tags[]`, `experiment_run_metrics`, bootstrap project, indexes |
| `supabase/config.toml` | new — local Supabase stack (project_id `tt_pangu`) |
| `supabase/.gitignore` | new — ignore `.temp/`, `.branches/` |
| `Makefile` | new — `supabase-up/down/reset/psql/status`, `test/test-smoke/test-db-smoke`, `kca-*` |
| `tools/kca/db.py` | new — psycopg3 access layer (13 public symbols) |
| `tools/kca/run.py` | rewritten — DB-first; FS becomes cache |
| `tools/kca/kaggle.py` | extended — best-effort approval-event recording on block |
| `tools/kca/COMMANDS.md` | updated — Approval recording section + artifact storage pointer |
| `tests/conftest.py` | new — shared fixtures (`unique_competition`, `cleanup_run_dir`, `db_url`) |
| `tests/test_kca_db_smoke.py` | new — 5 DB smoke cases (skippable w/o env) |
| `tests/test_kca_smoke.py` | updated — `@requires_db` markers on DB-dependent tests; env scoping on kaggle tests so they don't leak |
| `docs/adr/0008-artifact-storage-local-first.md` | new — ADR for `local://` URI scheme |
| `docs/design-decisions.md` | updated — ADR-008 entry |
| `docs/tooling/local-supabase.md` | new — full local Supabase walkthrough (+ psycopg dep note) |
| `docs/tooling/m2-schema-changes.md` | new — 0002 migration rationale |
| `docs/tasks/m2/M2-T001..T008-*.md` | new — 8 task specs |

Total: 11 commits, ~2,200 LoC added.

## Behavior added

- **Control plane on Postgres.** Runs and metrics live in the DB; the
  filesystem layout `runs/<comp>/<run_id>/` is now a cache.
- **Approval bridge.** Blocked Kaggle ops insert a `pending`
  `human_decisions` row carrying the attempted command, options, and a
  human-readable prompt. The CLI envelope returns the new row's id so a
  future inbox UI / CLI can resolve it.
- **Local Supabase workflow.** `make supabase-up` brings the stack online
  in 1–3 minutes (Docker pulls), with both migrations applied. `make
  supabase-psql`, `make test-db-smoke`, `make kca-runs` round out the
  day-to-day surface.

## Risks

- **kca is online-required for `run *` commands.** A developer who forgets
  `make supabase-up` will see a clean "DB unavailable" error and exit 1.
  Acceptable per the design decision (DB = truth) but worth noting.
- **`tools/kca/kaggle.py` imports `import kaggle` at the top of `kca.py`**
  which currently resolves to our local module because `tools/kca/` is on
  sys.path first. If anyone runs kca from a dir where PyPI `kaggle` is
  importable, shadow could break. M3 follow-up: rename `kaggle.py` → `kg.py`
  inside `tools/kca/`.
- **No CI for the DB smoke suite yet.** Running tests in CI needs either
  `supabase start` or a docker postgres step in the workflow. Documented in
  the M2-T007 spec as a follow-up.
- **Bootstrap project id is hard-coded** (`00000000-…-0001`). Fine for
  M2's single-user local dev. M3+ needs a real project model + auth.

## Approval needs

None — M2 introduces no remote-write paths.

## M3 follow-ups (suggested, not committed)

1. Rename `tools/kca/kaggle.py` → `tools/kca/kg.py` to avoid shadowing the
   PyPI `kaggle` package.
2. Worker spike — minimal Claude Agent SDK worker that consumes
   `agent_jobs` rows and writes to `experiment_runs`.
3. CI: add a GitHub Actions job that runs `supabase start` + the DB smoke
   suite on every PR.
4. CLI: `kca decisions list --pending` to surface pending approvals.
5. Move the kaggle gate from env-var to "approved `human_decisions` row
   exists for this attempt" once the approval surface exists.
6. Wire the real `kkr.py` into `kca kaggle submit | push | upload`.

## Reproducible exit check

```bash
# Bring up Postgres with both migrations applied.
docker run --rm -d --name kca-pg -e POSTGRES_PASSWORD=postgres -p 54399:5432 postgres:15
sleep 3
cat supabase/migrations/0001_init.sql | docker exec -i kca-pg psql -U postgres -d postgres -v ON_ERROR_STOP=1
cat supabase/migrations/0002_kca_run_alignment.sql | docker exec -i kca-pg psql -U postgres -d postgres -v ON_ERROR_STOP=1

# Run the full suite.
export KCA_DB_TARGET=local
export SUPABASE_DB_URL="postgres://postgres:postgres@127.0.0.1:54399/postgres"
python -m pytest tests/ -v   # 11 passed

docker stop kca-pg
```

End-to-end manual loop:

```bash
python tools/kca/kca.py run init --competition titanic --hypothesis "logistic baseline" --json
python tools/kca/kca.py run record-metric --run-dir runs/titanic/<ts> --key cv_score --value 0.823 --json
python tools/kca/kca.py run list --competition titanic --json
KCA_ALLOW_REMOTE= python tools/kca/kca.py kaggle submit --competition titanic --file submission.csv --message "v1" --json
# → exit 2, approval_request_id present.
```
