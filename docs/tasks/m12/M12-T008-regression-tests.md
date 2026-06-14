# M12-T008: E2E + smoke tests

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Add two test files that lock in the M12 regression surface:

1. `tests/test_m12_e2e.py` — dry-run path, **no credentials**, **no
   real network**. Mirrors `tests/test_m9_e2e.py` / `tests/test_m10_e2e.py`
   pattern. CI's `no-db` job picks it up.
2. `tests/test_m12_smoke.py` — DB-gated assertions against the rows
   M12-T002 / T006 / T007 wrote. CI's `live-db` job picks it up.

The e2e test must NOT hit `devpost.com`. The smoke test must NOT
write to the DB; it only reads.

## Tag

`test-gap:`. Routine.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M12
3. `docs/milestones/m12/loop-prompts.md` Loop Prompt 8
4. `tests/test_m9_e2e.py` — dry-run pattern, no creds
5. `tests/test_m9_smoke.py` — DB-gated pattern
6. `tests/test_m10_e2e.py` (if present) — most recent dry-run pattern
7. `src/worker/worker.py` — `dry_run` path
8. `tools/kca/devpost.py` (T003 + T007 surface)
9. `tools/kca/submission_checklist.py` (T004 output)
10. `services/decision_api/app.py` and `services/decision_api/tests/`
11. `.github/workflows/test.yml` — no-db + live-db job definitions

## Scope

1. Add `tests/test_m12_e2e.py` (5–6 tests; runtime < 5s):
   - **test_submission_pack_templater_idempotency** — call the
     submission_pack assembler twice; assert byte-identical output.
   - **test_submission_checklist_deterministic** — feed a fixed
     `submission_format` jsonb + fixture submission_pack directory;
     assert deterministic JSON output (golden file under
     `tests/fixtures/m12/`).
   - **test_devpost_submit_refusal_without_creds** — call
     `tools/kca/devpost.py::cmd_submit` with `DEVPOST_*` env vars
     unset; assert non-zero exit + the refusal message + ZERO network
     calls (verify via a sentinel that pytest can patch the HTTP
     client to raise on any request).
   - **test_decision_api_approval_roundtrip** — POST a
     `target_op="devpost_submit"` decision; assert it lands in the
     queue; approve via the decision_api endpoint; assert state
     transition. Uses the same fake-supabase fixture M9 / M10 e2e
     tests use.
   - **test_audit_no_devpost_network** — run the dry-run path; grep
     the audit log for any `devpost.com` HTTP line; assert 0 hits.
2. Add `tests/test_m12_smoke.py` (5–6 DB-gated assertions; SKIP when
   `SUPABASE_DB_URL` is unset):
   - The picked-slug `competitions` row has
     `competition_type='devpost'` (or `'hackathon_devpost'` if
     ADR-0018 picked that).
   - At least one `teams` row exists with a matching
     `team_memberships` row.
   - `experiment_runs` row exists with
     `metric_name='checklist_completion'` and `metric_value > 0`.
   - `submissions` row exists with `platform='devpost'` and a
     non-empty `external_submission_id` (or SKIP this assertion if
     T007 has not yet run; mark the test `xfail` until T007 closes).
   - `agent_reviews` + `human_decisions` rows exist for
     `target_op="devpost_submit"`.
   - Cross-milestone sanity: M9 / M10 baseline rows still resolve
     `competition_type='kaggle'`.
3. Add fixture files under `tests/fixtures/m12/`:
   - `submission_format.json` — sample jsonb
   - `submission_pack_minimal/` — minimal pack used by the
     idempotency + deterministic checklist tests
   - `golden_checklist.json` — expected checklist output
4. Ensure both test files run cleanly in CI:
   - `pytest tests/test_m12_e2e.py -q` exits 0 in the no-db job.
   - `pytest tests/test_m12_smoke.py -q` exits 0 in the live-db job
     (or all-skipped in no-db, with a clear skip reason).
5. Confirm no test makes a real Devpost HTTP call. Verify via the
   `test_audit_no_devpost_network` assertion AND by monkeypatching
   `urllib.request.urlopen` / `httpx.Client` to raise on any request
   during the e2e tests.

## Non-goals

- Do NOT add tests that require live Devpost credentials. Live
  validation is T007's job, not T008's.
- Do NOT add tests for the M9 / M10 regressions. Those have their own
  test files.
- Do NOT add tests against the UI. T005's vitest + Playwright cover
  the UI surface.
- Do NOT add a new CI job. The existing `no-db` and `live-db` jobs
  pick up `tests/test_m12_*.py` automatically.
- Do NOT add new pytest plugins / fixtures that affect M9 / M10
  test runs.

## Acceptance criteria

- `tests/test_m12_e2e.py` exists; 5–6 tests; all pass under the
  `no-db` configuration; runtime < 5s.
- `tests/test_m12_smoke.py` exists; 5–6 assertions; all pass under
  the `live-db` configuration; skip-with-reason under `no-db`.
- Fixture files exist under `tests/fixtures/m12/`.
- The e2e test's audit assertion confirms 0 `devpost.com` HTTP calls
  during the test run.
- `python -m pytest tests/ -q` passes; the existing M4 / M7 / M9 /
  M10 tests still pass.
- `ruff check .` clean.
- CI's `no-db` and `live-db` jobs both pick up the new files on the
  next push (verified by reading `.github/workflows/test.yml`; no
  workflow edit needed).

## Permissions

- File writes to: `tests/test_m12_e2e.py`, `tests/test_m12_smoke.py`,
  `tests/fixtures/m12/**`.
- No code changes outside `tests/`. (Source changes go through
  T002–T007.)
- No DB writes. The smoke test reads only.
- `git commit` / `git push` deferred to T009 closeout.

## Closeout format

```
M12-T008 closeout
  tests/test_m12_e2e.py: N tests, runtime <Xs (no-db config: PASS)
  tests/test_m12_smoke.py: N assertions (live-db: PASS, no-db: SKIPPED)
  tests/fixtures/m12/: <list of new fixture files>
  Audit assertion: 0 devpost.com network calls during e2e
  CI pickup: confirmed (no workflow file changes needed)
  Acceptance: PASS | FAIL — link to closing issue
  Risks / blockers: ...
  Next: M12-T009 (exit criteria + final review + closeout)
```

## Related issues

- Closing issue for M12 — gets a comment summarising test counts +
  fixture file paths.
- Issue #15 (decision_api: no GET /decisions) — if it lands before
  T008, the e2e test should use the GET path; otherwise stub it the
  way M9 / M10 e2e tests do.

## Stop condition

Stop after 80 turns. If any e2e test makes a real Devpost HTTP call,
HALT — the test is unsafe and must be sandboxed before it can ship.
If the smoke test detects a missing M9 / M10 baseline row (the M9
follow-up E or similar drift), HALT and file a follow-up issue; do
NOT loosen the assertion to "pass anyway".
