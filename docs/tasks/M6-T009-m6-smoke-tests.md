# M6-T009: M6 smoke tests

## Milestone
M6.

## Goal
12–14 pytest tests covering the M6 surface; all pass without any local
endpoint reachable, without Anthropic API key, and without Kaggle creds. A
single DB-dependent test skips cleanly when no DB.

## Read first
1. `tests/test_m5_smoke.py` (style + env-scrub helpers).
2. `src/worker/local_model.py`, `src/worker/reviewer.py`,
   `src/worker/telemetry.py`, `src/worker/triage.py`.
3. `tools/kca/local.py`, `tools/kca/review.py`.

## Required tests

1. `test_load_endpoints_from_env(monkeypatch)` — set 2 endpoints via
   monkeypatch; assert 2 LocalEndpoints, ordered, names match.
2. `test_load_endpoints_stops_at_gap(monkeypatch)` — set slot 0 + slot 2
   only; assert only slot 0 is returned.
3. `test_probe_unreachable_returns_ok_false()` — probe `http://127.0.0.1:1`;
   assert `ok=false`, `error` mentions connection.
4. `test_pick_endpoint_returns_none_when_all_down(monkeypatch)` — patch
   probe to always return ok=false; assert `pick_endpoint() is None`.
5. `test_routing_fallback_when_local_down(monkeypatch)` — patch
   `pick_endpoint` to None; `model_for("summarise")` returns the fallback
   model.
6. `test_reviewer_dry_run_approves()` — `Reviewer(dry_run=True).review(...)`
   → verdict=approve.
7. `test_reviewer_prompt_truncates_long_trace()` — feed >20 events; assert
   the rendered prompt is below the cap and ends with the JSON schema.
8. `test_otel_console_exporter_writes_to_stderr(capsys)` — span emitted
   under `KCA_OTEL_EXPORTERS=console` produces a stderr line.
9. `test_otel_sqlite_exporter_persists(tmp_path)` — emit one span; assert
   the SQLite file has the expected row.
10. `test_otel_disabled_writes_nothing(tmp_path, capsys)` — set
    `KCA_OTEL_ENABLED=0`; emit a span; nothing in stderr, no SQLite file.
11. `test_kca_local_list_no_db(monkeypatch)` — env has 1 endpoint;
    `kca local list --json` returns it with `db_warning` absent
    (local layer doesn't need DB).
12. `test_kca_review_list_no_db()` — `kca review list --json` returns
    `{ok: true, reviews: []}` with `db_warning`.
13. `test_kca_review_run_dry_run(tmp_path)` — feed a fake job event trail;
    `kca review run --job-id <synth> --dry-run --json` returns
    `verdict=approve`.
14. (DB-dependent, skip without `SUPABASE_DB_URL`)
    `test_review_round_trip()` — `create_review → get_review → list_reviews`
    consistency.

## Acceptance criteria
- `python -m pytest tests/test_m6_smoke.py -v` — all pass (1 SKIP without
  DB).
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 25 turns. If a test needs network it doesn't have, monkeypatch
`requests.get` (or the local-model HTTP layer) to a deterministic mock
rather than spinning up a real server.
