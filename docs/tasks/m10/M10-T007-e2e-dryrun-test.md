# M10-T007: `tests/test_m10_e2e.py` dry-run end-to-end smoke

## Milestone
M10: live end-to-end regression test — Petals to the Metal.

## Goal
Add `tests/test_m10_e2e.py` that exercises the M10 pipeline in
dry-run mode — research → baseline notebook → kg-nb round-trip →
reviewer-gate (`kernel_push`) → decision approve → `kca kaggle push`
credentials-gate refusal — all WITHOUT real Kaggle credentials and
WITHOUT any real Kaggle network call. CI must collect it in both the
`no-db` and `live-db` jobs.

**HARD PRE-REQ: issue #11 (dotenv-leak) must be CLOSED on `main`
before this Loop Prompt may run.** The reason: the equivalent M9
test (`tests/test_m9_e2e.py::test_kca_kaggle_submit_refuses_without_credentials`)
inadvertently posted 3 ERROR submissions to the Spaceship Titanic
leaderboard because `tools/kca/db.py` re-injects `.env` credentials
into the subprocess regardless of `cwd`. If we run this Loop Prompt
without #11 closed, the equivalent M10 test will pollute the
`tpu-getting-started` leaderboard with null-score ERROR kernel
pushes — the same failure mode at higher cost (kernel pushes count
against a daily limit).

This task assumes **M10-T006 closeout is PASS** AND **issue #11 is
CLOSED**.

## Read first

1. `tests/test_m9_e2e.py` (the closest pattern; learn from its leak)
2. `tests/test_m9_smoke.py` (DB-gated pattern)
3. `tests/test_m8_smoke.py`, `tests/test_m8_worker_wiring.py` (older
   patterns)
4. `src/worker/worker.py` (dry_run path)
5. `tools/kca/kg.py::cmd_push` (gating without `KAGGLE_USERNAME` /
   `KAGGLE_KEY`)
6. Issue #11 (the leak this test must NOT repeat)
7. `docs/tasks/m9/M9-T007-e2e-dryrun-test.md` (the precedent)

## Scope

Before writing the test, verify issue #11 is closed:

```
gh issue view 11 --json state
```

Must report `"CLOSED"`. If not, HALT and ask.

Then add `tests/test_m10_e2e.py` with tests covering:

1. **Baseline notebook smoke** — author a tiny notebook against
   fixture data under `tests/fixtures/tpu-getting-started/` (a 2-class,
   ~80-image stub — not the real 104-class dataset). Verify the
   notebook executes top-to-bottom locally in < 60s.

2. **kg-nb round-trip** — convert the notebook to percent-format `.py`,
   convert back, assert the cell sequence and outputs are equivalent
   (modulo execution timestamps).

3. **Reviewer-gate + decision_api round-trip** — drive a stub worker
   that abstains at `kernel_push`; assert the `agent_reviews` +
   `human_decisions` rows land; approve via the decision_api (POST or
   `kca decisions approve`); assert state flip. Mocked DB OR live
   sandbox DB, depending on which CI job is running (decorate
   appropriately so `no-db` SKIPs cleanly).

4. **`kca kaggle push` credentials-gate refusal** — the most
   important and most fragile test. Mirror the M9 pattern with
   M9-T007's tightening + the #11 fix:
   ```python
   env = {
       "PATH": os.environ.get("PATH", ""),
       "HOME": str(tmp_path),  # so kaggle library can't find ~/.kaggle/kaggle.json
       "PYTHONPATH": str(REPO_ROOT),
       "KCA_SKIP_DOTENV": "1",  # honoured by tools/kca/db.py after #11
   }
   proc = subprocess.run(
       [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py"),
        "kaggle", "push",
        "--competition", "tpu-getting-started",
        "--notebook", "/dev/null",
        "--message", "m10-e2e dry-run — must refuse",
        "--json"],
       env=env, cwd=str(tmp_path),
       capture_output=True, text=True, timeout=30,
   )
   # MUST refuse via the credentials gate, not via a real kaggle CLI
   # error. Assert payload["ok"] is False AND payload["side_effect"] ==
   # "KERNEL_PUSH" (or whatever cmd_push's literal is) AND
   # payload["error"] contains "KAGGLE_USERNAME" or "KAGGLE_KEY".
   ```

5. **Audit-grep regression sentinel** — after the test suite runs,
   assert that `.agent/audit/tool-events.jsonl` (or equivalent) has 0
   lines whose command starts with `kaggle kernels push` or
   `kca kaggle push` for the M10-T007 process. This is the explicit
   guard against repeating the M9 leak. If issue #11 is not yet
   honoured by `tools/kca/db.py::load_dotenv`, this assertion FAILs
   and the test stops — that's the intended interlock.

6. **Submission-shape sanity** — for fixture data, generate a
   miniature notebook output and assert its kernel-metadata.json
   parses against `kaggle kernels init` schema (no real CLI call;
   schema validation only).

## Non-goals

- No real Kaggle network calls. None.
- No real `kaggle kernels push`. None.
- No new fixtures bigger than ~5 MB total (the fixture is for shape,
  not for training quality).
- Do not extend `tools/kca/kg.py::cmd_push` — that's M10-T002 / #11.
- Do not file #11's fix from this Loop Prompt; if #11 is open, halt
  and ask.

## Acceptance criteria

- `tests/test_m10_e2e.py` exists; ~6 tests; total runtime < 60s; no
  net, no DB, no credentials.
- The credentials-gate refusal test verifiably refuses BEFORE the
  kaggle CLI is invoked. Evidence: payload["error"] contains the
  credential-key literal; audit-grep finds 0 lines for the test
  process matching the real push command.
- `pytest tests/test_m10_e2e.py -v` PASSes with `SUPABASE_DB_URL`
  set; SKIPs cleanly without it.
- `pytest tests/ services/decision_api/tests` matches M10-T006
  baseline + the new tests, 0 regressions.
- `.github/workflows/test.yml` collects the new file in both
  `no-db` and `live-db` jobs (the existing path patterns already
  catch `tests/test_*.py`; verify in the closeout).
- `ruff check .` + `ruff format --check .` clean.
- Audit-grep guard PASSes: no kernel-push command leaked from the
  test process to the kaggle CLI.

## Permissions

- `git commit` and `git push` deferred to milestone closeout.
- No real Kaggle calls.
- Test fixtures can be force-added if needed (small slices only).

## Closeout format

```
M10-T007 closeout
  New file: tests/test_m10_e2e.py (<n> tests, all PASS, <m>s wall)
  Fixtures: tests/fixtures/tpu-getting-started/<...> (small slice; total <p> MB)
  pytest result: <n> passed, 0 failed, network=NO, db=<NO|SKIP without env>
  Credentials-gate refusal asserted: YES (with payload["error"] containing KAGGLE_USERNAME or KAGGLE_KEY literal)
  Audit-grep guard: 0 lines matching `kaggle kernels push` or `kca kaggle push` from this test process
  Full baseline: <X> passed / <Y> skipped (was <X-Z> / <Y>, +Z new tests, 0 regressions)
  ruff check + ruff format --check: clean
  CI pickup: YES — .github/workflows/test.yml no-db and live-db jobs both run pytest tests/ recursively
  Issue #11 state at run time: CLOSED — verified via `gh issue view 11 --json state`
  Acceptance: PASS | FAIL — link to issue
  Next: M10-T008 ready to start (final review + worktree-milestone-pr)
```

## Related issues

- #11 — HARD PRE-REQ. Must be CLOSED before T007 runs. The whole
  reason this task exists in this shape.
- #12 — M10 proposal.
- #15 — decision_api `GET /decisions`. If still open, the reviewer-
  gate round-trip test reads via direct DB.

## Stop condition

Stop after 60 turns. If issue #11 is OPEN at run time, HALT and ask —
do NOT write a test that would repeat the M9 leak on a kernel-push
endpoint that has stricter rate limits. If the audit-grep guard FAILs
(any line matches the real push command), HALT, investigate the leak
path, and surface — that is exactly the regression sentinel this
test is designed to catch.
