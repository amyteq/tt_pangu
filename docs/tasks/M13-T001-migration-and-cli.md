# M13-T001: Migration 0010 + `kca eval` CLI scaffold

## Milestone
M13: evaluation, reliability, and regression suite.

## Goal
Land the three new tables (`eval_suites`, `eval_runs`,
`eval_results`) via `supabase/migrations/0010_m13_eval.sql`, the
matching helper functions in `tools/kca/db.py`, and the `kca eval`
top-level subcommand surface with four placeholder verbs (`list`,
`run`, `show`, `report`). No suites yet; the scaffold must exit-0
on `--help` for every verb, and `run` must refuse with
`NO_SUITES_REGISTERED` until T002+ register their suites.

This task assumes **M13-T000 closeout is PASS** and the M13 proposal
issue has reached `decision:confirmed` + `ai:ready`.

## Read first

1. M13-T000 closeout (ADR-0019 + architecture doc).
2. `docs/adr/0019-eval-regression-suite.md` (the schema this task
   implements).
3. `docs/architecture/eval-regression-suite.md` (table layouts).
4. `supabase/migrations/0007_m8_agent_tool_audit.sql` (most recent
   migration; idempotency posture).
5. `supabase/migrations/0006_m6_reviews_spans.sql` (the M6 two-table
   pattern is close to what `eval_runs` + `eval_results` need).
6. `tools/kca/db.py` (existing helper functions — the new ones
   follow the M6 / M8 naming convention).
7. `tools/kca/kca.py` (top-level subcommand registration).
8. `tools/kca/run.py` (LOCAL_WRITE pattern; gating; JSON-output
   convention).
9. `docs/architecture/kca-cli-architecture.md` (where the new
   subcommand sits in the four-layer model).
10. `tests/test_m4_smoke.py` and `tests/test_m5_smoke.py` (migration
    test patterns — extending one of these for T008's smoke is
    out of scope here, just understand the shape).

## Scope

1. **Migration `supabase/migrations/0010_m13_eval.sql`** —
   idempotent (`CREATE TABLE IF NOT EXISTS …`):

   - `eval_suites` — `id uuid pk`, `name text unique not null`,
     `description text`, `version text not null`, `category text
     check (category in ('tool_smoke','kaggle_replay','kernel_dryrun','reasoning','model_route_compare'))`,
     `metadata jsonb default '{}'::jsonb`, `created_at timestamptz
     default now()`.
   - `eval_runs` — `id uuid pk`, `started_at timestamptz default
     now()`, `finished_at timestamptz`, `route text not null`,
     `dry_run bool not null default true`, `total_cases int not null
     default 0`, `total_pass int`, `total_fail int`, `total_skip
     int`, `aborted_on_budget bool default false`, `budget_usd
     numeric(10,4)`, `cost_usd numeric(10,4)`, `metadata jsonb
     default '{}'::jsonb`.
   - `eval_results` — `id uuid pk`, `run_id uuid not null references
     eval_runs(id) on delete cascade`, `suite_id uuid not null
     references eval_suites(id)`, `case_name text not null`,
     `route text not null`, `status text not null check (status in
     ('pass','fail','skip','error'))`, `metrics jsonb default
     '{}'::jsonb`, `latency_ms int`, `cost_usd numeric(10,4)`,
     `error_text text`, `created_at timestamptz default now()`.
   - Indexes: `(run_id)` on results; `(suite_id, route)` on
     results; `(started_at desc)` on runs; `(category)` on suites.

2. **DB helpers in `tools/kca/db.py`** — pure-Python, no business
   logic:
   - `register_eval_suite(name, description, version, category,
     metadata) -> str` (returns suite uuid; idempotent on `name`).
   - `start_eval_run(route, dry_run, budget_usd, metadata) -> str`.
   - `finish_eval_run(run_id, totals_dict, cost_usd,
     aborted_on_budget)` .
   - `record_eval_result(run_id, suite_id, case_name, route,
     status, metrics, latency_ms, cost_usd, error_text) -> str`.
   - `list_eval_suites(category=None) -> list[dict]`.
   - `list_eval_runs(limit=20) -> list[dict]`.
   - `fetch_eval_results(run_id) -> list[dict]`.

3. **`kca eval` CLI scaffold** —
   `tools/kca/eval.py` exports `add_parsers(subparsers)` registered
   from `tools/kca/kca.py`. Verbs:
   - `kca eval list [--json]` — lists registered suites (empty until
     T002+).
   - `kca eval run [--suite NAME ...] [--all] [--route ROUTE]
     [--dry-run] [--budget USD] [--json]` — at this point refuses
     with `{"ok": false, "error": "NO_SUITES_REGISTERED"}` if no
     suites are registered. When suites land in T002+ this becomes
     the entry point for the harness.
   - `kca eval show <run_id> [--json]` — prints the rolled-up rows
     for a given run.
   - `kca eval report <run_id> [--json | --md] [--out PATH]` — at
     this point a thin shim that defers to T007's aggregator;
     prints `{"ok": false, "error": "REPORT_AGGREGATOR_NOT_YET_IMPLEMENTED"}`.

4. **Suite-registration entry point.** Define a `register_all()`
   hook in `tools/kca/eval/__init__.py` that auto-discovers
   `tools/kca/eval/suites/*/__init__.py` modules and calls each
   module's `register(db)` function. T001 ships the discovery
   plumbing but no suites; T002+ add the suite modules.

5. **Smoke evidence** (not the formal test suite — that lands in
   T008):
   - `python -m tools.kca.kca eval --help` prints the four verbs.
   - `python -m tools.kca.kca eval list --json` prints `{"suites":
     [], "count": 0}`.
   - `python -m tools.kca.kca eval run --all --dry-run --json`
     prints `{"ok": false, "error": "NO_SUITES_REGISTERED"}`.
   - Connecting to the local Supabase DB with
     `SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`,
     verify the three new tables exist via `psql -c "\\d eval_suites"`
     etc.

## Non-goals

- Do not implement any suite drivers in this task. T002 (tool-smoke)
  is the first suite.
- Do not implement the report aggregator. T007 owns it.
- Do not modify existing migrations.
- Do not add new top-level CLI subcommands beyond `kca eval`.
- Do not call real Kaggle / LLM endpoints.

## Acceptance criteria

- `supabase/migrations/0010_m13_eval.sql` applies cleanly via
  `psql $SUPABASE_DB_URL -f supabase/migrations/0010_m13_eval.sql`
  twice in a row (idempotent).
- `tools/kca/db.py` exports the seven helpers in scope step 2;
  `ruff check .` and `ruff format --check .` clean.
- `kca eval --help` lists the four verbs.
- `kca eval list --json` prints empty-suite JSON.
- `kca eval run --all --dry-run --json` prints the
  `NO_SUITES_REGISTERED` refusal.
- `kca eval show <random-uuid>` exits non-zero with a clean
  `{"ok": false, "error": "NOT_FOUND"}`.
- No regressions in `pytest tests/ services/decision_api/tests`.

## Permissions

- `git add` / `git commit` deferred to milestone closeout.
- LOCAL_WRITE (Supabase) — applies new migration; ALLOWED at this
  prompt.
- No real Kaggle / LLM calls.

## Closeout format

```
M13-T001 closeout
  Migration: supabase/migrations/0010_m13_eval.sql (applied; idempotent verified)
  DB helpers: tools/kca/db.py +<n> functions (register_eval_suite, start_eval_run, finish_eval_run, record_eval_result, list_eval_suites, list_eval_runs, fetch_eval_results)
  CLI: kca eval list/run/show/report — registered; `kca eval --help` prints 4 verbs
  NO_SUITES_REGISTERED refusal: verified via `kca eval run --all --dry-run --json`
  pytest: <X> passed / <Y> skipped (was <X> / <Y>; 0 regressions)
  ruff check + ruff format --check: clean
  Acceptance: PASS — scaffold ready for T002+
  Next: M13-T002 (tool-smoke suite — first concrete suite driver)
```

## Related issues

- M13 proposal issue (closes on the M13 PR merge).

## Stop condition

Stop after 60 turns. HALT and ask if:
- The migration cannot be applied idempotently — investigate
  before retrying.
- The `kca eval` subcommand registration collides with an existing
  one (it should not — `eval` is new).
- The DB helpers expose any function name that already exists in
  `tools/kca/db.py`. Rename to avoid collision.
