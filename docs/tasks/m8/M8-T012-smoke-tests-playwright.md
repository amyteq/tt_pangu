# M8-T012: Smoke tests + Playwright

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 12; extracted here for the double-layer convention.

## Goal
`tests/test_m8_smoke.py` (Python, 12–15 tests) + `ui/tests/e2e/m8.spec.ts`
(Playwright, 4 tests). All pass without `ANTHROPIC_API_KEY`, `KAGGLE_KEY`,
or real network egress; live-DB-dependent tests use the `@pytest.mark.db`
gate.

## Read first
1. `tests/test_m7_smoke.py` (Python smoke style)
2. `tools/kca/agent/audit.py` (`insert_tool_audit`, `AuditLogger`)
3. `tools/kca/agent/skill_loader.py` (`SkillValidationError`)
4. `services/decision_api/app.py` (action endpoints)
5. `ui/src/pages/*.tsx` (page IDs for Playwright selectors)

## Scope / Files / Implementation guidance

### Required Python tests (use these names verbatim)
1. `test_tool_audit_table_present_on_db_target [db]`
   Reads `pg_catalog` to confirm `agent_tool_audit` + view exist.
2. `test_tool_audit_dual_write_jsonl_only(tmp_path)`
   With `SUPABASE_DB_URL` unset, `AuditLogger(backend='both')` still
   writes the JSONL line and does NOT raise.
3. `test_skill_schema_rejects_bad_name(tmp_path)`
   `load_skill` on a SKILL.md with name "Bad Name" raises `SkillValidationError`.
4. `test_skill_schema_rejects_unknown_tool(tmp_path)`
   `allowed-tools` containing `"made_up_tool"` raises `SkillValidationError`.
5. `test_skill_fixture_no_longer_in_kca_skills()`
   `.kca/skills/_test_fixture` does NOT exist on disk.
6. `test_skill_fixture_still_loadable_from_tests_root()`
   `load_skill('_test_fixture', skills_root=tests/fixtures/skills)` works.
7. `test_worker_tool_call_allow_path(monkeypatch)`
   Approval gate `"allow"` → tool executes, audit row recorded.
8. `test_worker_tool_call_ask_path(monkeypatch)`
   Approval gate `"ask"` → no side effect, `human_decisions` row created,
   audit row "ask".
9. `test_worker_tool_call_deny_path(monkeypatch)`
   Approval gate `"deny"` → no side effect, job `status="failed"`,
   audit row "deny".
10. `test_decision_api_approve_idempotent(client)`
    Two POSTs to `/decision/:id/approve` → first 200, second 409.
11. `test_decision_api_reject_minlength(client)`
    POST `/decision/:id/reject` with reason of length 7 → 400.
12. `test_decision_api_ask_improve_appends_event(client)`
    Successful call appends `agent_job_events("feedback")` row.
13. `test_kca_skill_run_execute_creates_job(monkeypatch)`
    `kca skill run triage-log --arg job_id=... --execute --json` returns
    a `job_id`; `agent_jobs` row exists.

### Required Playwright tests (`ui/tests/e2e/m8.spec.ts`)
1. `dashboard_has_four_sections` — visits `/`, asserts 4 section headings.
2. `approvals_inbox_lists_pending` — visits `/approvals`, asserts table
   row count matches a seeded fixture (use Supabase docker test fixture).
3. `decision_gate_blocks_short_reason` — types 5-char reject reason,
   "Reject" button stays disabled; types 10 chars, becomes enabled.
4. `external_link_has_noopener` — every `<a target="_blank">` on `/research`
   has `rel="noopener noreferrer"`.

## Acceptance criteria
- `python -m pytest tests/test_m8_smoke.py -v` → 13/13 pass (db-marked
  tests run only when `SUPABASE_DB_URL` is set)
- `cd ui && pnpm exec playwright install --with-deps chromium`
- `cd ui && pnpm exec playwright test` → 4/4 pass
- `python -m pytest tests/ -v -m "not db"` → 0 failures total

Report: per-test status, Playwright trace location, any flaky test re-run count.

## Stop condition
Stop after 30 turns.
