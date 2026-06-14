# M5-T010: M5 exit criteria + final review

## Milestone
M5: research and browser workflow.

## Goal
Verify all M5 exit criteria before declaring M5 done. Mirror the M4 exit
sequence in shape; produce `docs/milestones/m4/final-review.md`'s sibling file.

## Read first
1. `docs/milestones/m4/final-review.md` (template)
2. `docs/milestones/README.md` (M5 exit criteria)
3. All M5 task specs (T000..T009)

## Checklist

### Schema + DB (requires `SUPABASE_DB_URL`)
1. Migration 0005 applies cleanly; re-apply produces only `NOTICE` lines.
2. `research_items` shows the 8 new columns.
3. `research_citations` table exists.

### Research CLI
4. `kca research --help` lists `fetch | add | list | show | cite`.
5. `kca research fetch --url http://localhost/ --json` returns `ok=false`
   with a private-net warning.
6. `kca research fetch` against a local fixture HTTP server writes
   `artifacts/research/<hash>/{raw.html,main.txt}` and inserts DB rows when
   DB is up.
7. `kca research list` exits 0 without DB.

### Approval gate
8. `JobPolicy.approval_gates['external_fetch'] == False`.
9. `_check_approval_gate('external_fetch', {'approval_gates': {'external_fetch': True}})`
   raises `ApprovalRequired`.

### Kaggle download + verify
10. `kca kaggle download --resume` skips already-hashed files.
11. `kca kaggle verify` reports `ok=true` on intact data, `ok=false` on tamper.

### Resume paused jobs
12. End-to-end pause → approve → resume cycle leaves `agent_job_events`
    with `approval_pause` → `approval_resume` → `done`.

### Model routing
13. `model_for('eval')` is Opus; `model_for('implement')` is Sonnet.
14. `scripts/run_job.py --job-type analysis` records the Opus model id in
    the printed JSON.

### CI
15. `.github/workflows/test.yml` runs the `no-db` job successfully (verify
    by `act` or by pushing a temp branch).

### TC-2 House Prices
16. All 7 checks from M5-T008 PASS.

### Test suite
17. `python -m pytest tests/ -v` → 0 failures (no-DB).
18. `python -m pytest tests/ -v` with `SUPABASE_DB_URL` set → 0 failures.

## Output

1. Print a validation matrix table.
2. If all non-SKIP checks PASS: emit `M5 EXIT CRITERIA MET`.
3. Create `docs/milestones/m5/final-review.md` (mirror M4 template) with:
   - validation matrix
   - changed-files table
   - notes on browser/research design
   - **M6 follow-ups** section (route table tuning, multi-agent review,
     local vLLM/Ollama path, telemetry dashboard).

## Stop condition
Stop after 30 turns. Do NOT git add or commit.
