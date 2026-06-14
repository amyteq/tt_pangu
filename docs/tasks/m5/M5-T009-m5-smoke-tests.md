# M5-T009: `tests/test_m5_smoke.py`

## Milestone
M5: research and browser workflow.

## Goal
Add 10–12 smoke tests that exercise M5 surfaces without needing real
network, Kaggle credentials, Anthropic key, or a live DB.

## Read first
1. `tests/test_m4_smoke.py` (style + env scrub helpers)
2. `tools/kca/research.py` (T003)
3. `tools/kca/research_fetch.py` (T002)
4. `tools/kca/kg.py` (T004 download/verify)
5. `src/worker/routing.py` (T006)

## Required tests

1. `test_research_fetch_refuses_localhost()` — `fetch_page("http://localhost/")` → `ok=False`.
2. `test_research_fetch_against_local_server(tmp_path)` — spin up
   `http.server` on an ephemeral port serving a fixture HTML; assert raw.html
   + main.txt + non-empty `content_hash`.
3. `test_research_add_no_db(tmp_path)` — `kca research add --url ... --json`
   exits 0 with `db_warning` when `SUPABASE_DB_URL` is unset.
4. `test_research_list_no_db()` — `kca research list --json` → `{"ok": true, "items": []}`.
5. `test_kaggle_download_verify_roundtrip(tmp_path)` — seed manifest +
   files; `kca kaggle verify` → `ok=true`.
6. `test_kaggle_download_verify_mismatch(tmp_path)` — tamper one file;
   verify reports `mismatched`.
7. `test_model_routing_defaults()` — `routing.model_for("eval")` is Opus,
   `"implement"` is Sonnet.
8. `test_model_routing_override()` — `model_for("eval", override="claude-haiku-4-5")` is Haiku.
9. `test_run_job_job_type_flag()` — `scripts/run_job.py --prompt p --dry-run --job-type analysis --json`
   exits 0 and the printed `model` matches Opus.
10. `test_external_fetch_gate_blocks()` — `_check_approval_gate("external_fetch", {...True})`
    raises `ApprovalRequired`.
11. `test_external_fetch_gate_allows_default()` — does not raise with the default policy.
12. `test_resume_paused_dry_run(tmp_path)` — `scripts/run_job.py --job-id ...`
    against a job pre-seeded with `paused` rows in `agent_job_events`
    completes without re-running prior turns (asserts `turns_used` accumulates).

## Acceptance criteria
- `python -m pytest tests/test_m5_smoke.py -v` — all pass.
- Full suite `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 50 turns.
