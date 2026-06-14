# M11-T008: E2E + smoke tests (dry-run + refusal paths, no credentials, no net)

## Milestone
M11: authorized CTF / lab workflow.

## Goal
Add `tests/test_m11_e2e.py` + `tests/test_m11_smoke.py` to lock the M11
workflow in CI: dry-run path runs without credentials, refusal paths
hard-deny out-of-scope targets, and no test echoes `.env` / `~/.ctf/*`
contents.

## Read first

1. `tests/test_m9_e2e.py` — closest pattern (Kaggle dry-run e2e)
2. `tests/test_m9_smoke.py` — DB-gated assertion pattern
3. `tests/test_m10_e2e.py` (if M10 has shipped) — kernel-push refusal
   shape; mirror it for `flag_submit` / `challenge_run`
4. `src/worker/worker.py` — `dry_run` path
5. `tools/kca/ctf.py::cmd_flag_submit` — credential-gate refusal
6. M11-T002 / T003 / T004 / T005 closeouts
7. Issue #11 — the dotenv-leak this test must NOT repeat

## Soft pre-req

Issue #11 (dotenv-leak / secret-file hygiene in pytest subprocess)
**should** be merged on `main` before this Loop Prompt runs. Verify with
`gh issue view 11 --json state` returns `"CLOSED"`. If #11 is not yet
closed, do NOT write any test that subprocess-shells in a way that would
inherit `.env` or `~/.ctf/*` to the child. The simpler form (no
subprocess; in-process import of CLI functions) is acceptable as a
workaround, but the closeout MUST note the deviation.

## Scope

1. **`tests/test_m11_e2e.py`** — five tests, no DB, no credentials, no
   network:

   **(a) `test_flag_submit_refused_without_approval`** — invoke
   `tools.kca.ctf.cmd_flag_submit` with `--dry-run=False` but no prior
   approval row; expect `RefusalError` (or whatever T003 / T006 wires)
   AND no POST attempt. Assert the audit row would have recorded
   `flag_submit` reject.

   **(b) `test_challenge_run_refused_for_out_of_scope_url`** — build a
   fake job context with a `ctf_scopes.target_urls` row covering
   `http://localhost:8080` only; attempt `challenge_run` against
   `http://example.com`. Expect refusal via the `network_egress`
   policy.

   **(c) `test_network_egress_denied_to_kaggle_from_ctf_job`** — same
   shape as (b) but with `https://www.kaggle.com` as the out-of-scope
   target. Cross-platform isolation: a CTF job MUST NOT touch Kaggle.

   **(d) `test_bundled_solver_roundtrip_local`** — using the T004
   fixtures, run the web solver against a recorded HTTP response
   (mocked via `respx` / `httpx_mock` to avoid bringing docker up in
   CI) and the crypto solver in-process. Expect both flags recovered
   and verified against `expected.sha256`. Assert the flag string
   appears nowhere in stdout / stderr.

   **(e) `test_no_secret_leak_in_test_stdout`** — run the full file's
   tests with `pytest --capture=tee-sys`; grep the captured output
   for any line that looks like `KCA_TOKEN=`, `CTF_*_TOKEN`, a
   ~/.ctf/*.json line, or a flag pattern. Assert 0 matches. This
   test is the M11 analogue of the M10 dotenv-leak regression and
   directly closes issue #11 from the CTF side.

2. **`tests/test_m11_smoke.py`** — DB-gated assertions (mirror M9 / M10
   smoke shape):
   - Migration `0008_m11_ctf.sql` applied (tables present).
   - `ctf_events` contains the past-event row from T004.
   - `ctf_challenges` contains 2 rows (web + crypto) for that event.
   - `ctf_scopes` contains the matching scope rows.
   - `agent_reviews` has at least 2 rows with
     `target_op in ('challenge_run','flag_submit')` from T006.
   - `ctf_attempts` has at least 2 rows with `accepted=true` from
     T005 + the T006 LOCAL_WRITE row + (if T007 ran) the live row.
   SKIPs cleanly without `SUPABASE_DB_URL`.

3. **CI integration.** Confirm the new tests are picked up by the
   existing `.github/workflows/test.yml` no-db + live-db jobs. No new
   workflow file. If `pytest -q tests/test_m11_e2e.py` exits clean on
   a fresh checkout (no `.env`, no `~/.ctf/`), the e2e test
   suite is portable.

4. **Audit-grep harness.** Add a small helper `tests/_audit_grep.py`
   (or extend an existing one if M9 / M10 already has it) that scans
   a captured pytest log for secret patterns + flag-format regexes.
   Use it in (e) above.

## Non-goals

- Do not write tests that subprocess-shell into the agent and inherit
  `.env` / `~/.ctf/*`. Use in-process imports.
- Do not write tests that make any real external network call.
- Do not bring `docker-compose` up in CI — mock HTTP responses for
  the web challenge in (d).
- Do not add `pytest --runslow` markers; the M11 e2e + smoke suites
  should run under the existing CI matrix.

## Acceptance criteria

- `python -m pytest tests/test_m11_e2e.py -v` → all 5 tests pass; 0
  network calls (verify with `pytest --capture=tee-sys | grep -c '
  GET http\|POST http'`).
- `python -m pytest tests/test_m11_smoke.py -v` → all pass with
  `SUPABASE_DB_URL`; SKIPs cleanly without.
- `python -m pytest tests/ services/decision_api/tests -v` → 0
  failures.
- `ruff check tests/` clean.
- Audit-grep helper detects synthetic secret-pattern + flag-pattern
  injections in a one-liner self-test.
- The M11 e2e test suite runs on a fresh checkout with no `.env`,
  no `~/.ctf/`, and 0 credentials — assert with a clean-env
  pytest invocation in the closeout.

## Permissions

- Local file writes under `tests/`.
- `pytest` invocations under sandbox (no DB / no net required).
- LOCAL_WRITE DB calls allowed for the smoke suite under
  `dangerouslyDisableSandbox=true`.
- No real external network calls.

## Closeout format

```
M11-T008 closeout
  tests/test_m11_e2e.py: 5/5 passed
  tests/test_m11_smoke.py: <n>/<m> passed (DB-gated, SKIP without SUPABASE_DB_URL)
  Audit-grep helper: 0 hits across pytest stdout/stderr
  Fresh-env run: pytest passed with no .env, no ~/.ctf/, no creds
  Issue #11 status at run time: CLOSED | OPEN (note deviation if OPEN)
  ruff check tests/: clean
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T009 ready to start
```

## Related issues

- M11 proposal issue (TBD). M11-T008 closes the "e2e + refusal-paths"
  bullet.
- Issue #11 — soft pre-req; the (e) test closes this from the CTF
  side regardless of #11's main-line fix.

## Stop condition

Stop after 80 turns. If any test ever produces a real network call,
HALT and refactor. If issue #11 is open AND a subprocess-shelling
test path is unavoidable, document the deviation and SKIP that test
until #11 closes — do not write a test that re-opens the leak.
