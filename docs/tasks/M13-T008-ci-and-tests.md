# M13-T008: CI nightly cron + `tests/test_m13_smoke.py` + `tests/test_m13_e2e.py`

## Milestone
M13: evaluation, reliability, and regression suite.

## Goal
Add the M13 test suite and CI plumbing:
- `tests/test_m13_smoke.py` — DB-gated (~6 tests): suites
  register, migration applied, aggregator emits parseable JSON.
- `tests/test_m13_e2e.py` — no-DB / no-creds / no-net (~6 tests):
  every suite runs in `--route mocked` end-to-end against
  checked-in fixtures against an ephemeral sqlite tmpdir DB,
  produces the expected `eval_results` rows.
- `.github/workflows/eval.yml` — scheduled nightly cron
  (03:30 UTC). Runs `kca eval run --all --route mocked --json`,
  uploads the JSON report as a workflow artefact, and `gh issue
  comment`s the rolling diff against the previous nightly. Never
  touches real Kaggle or real LLM APIs.

**Hard pre-req: issue #11 (dotenv leak) is CLOSED** — same posture
as M10-T007. The nightly cron's subprocess invocations must not
re-introduce the leak.

This task assumes **M13-T007 closeout is PASS**.

## Read first

1. M13-T001 through M13-T007 closeouts.
2. `.github/workflows/test.yml` (existing CI shape; the new
   workflow lives alongside it).
3. `tests/test_m9_smoke.py` + `tests/test_m9_e2e.py` (closest
   pattern — M13 mirrors the smoke/e2e split).
4. `tests/test_m10_e2e.py` — the audit-grep regression sentinel
   pattern; M13 inherits it.
5. `tools/kca/eval/` (the T001–T007 surface tested here).
6. `runs/m13-eval/` (the snapshot directory the workflow writes
   to and uploads).
7. Issue #11 state via `gh issue view 11 --json state` — must
   return `"CLOSED"`.

## Scope

Before any test or workflow file is touched, verify issue #11 is
closed:

```bash
gh issue view 11 --json state
```

Must report `"CLOSED"`. If not, HALT and ask.

1. **`tests/test_m13_smoke.py`** (DB-gated; ~6 tests):
   - `test_migration_0008_applied` — `eval_suites`,
     `eval_runs`, `eval_results` exist; SKIP if no
     `SUPABASE_DB_URL`.
   - `test_db_helpers_roundtrip` — `register_eval_suite` +
     `start_eval_run` + `record_eval_result` + `fetch_eval_results`.
   - `test_kca_eval_list_shows_registered_suites` — invokes the
     CLI as a subprocess; expects ≥5 suite names.
   - `test_kca_eval_run_creates_one_runs_row` — `kca eval run
     --suite tool-smoke --route mocked --dry-run --json`;
     assert `eval_runs` row count increments by 1.
   - `test_kca_eval_report_json_shape` — runs the aggregator
     against the latest run; asserts the `ReportPayload` shape
     (top-level keys present, `groups` non-empty).
   - `test_audit_grep_sentinel_clean` — after a full
     `kca eval run --all --route mocked --dry-run` subprocess
     completes, assert `.agent/audit/tool-events.jsonl` has 0
     lines matching `kaggle competitions submit | kaggle kernels
     push | kaggle datasets create | kaggle datasets version` for
     the test process.

2. **`tests/test_m13_e2e.py`** (no-DB; no-creds; no-net;
   ~6 tests): same structure as the smoke tests but with the
   DB swapped for an ephemeral sqlite tmpdir DB via a fixture.
   Environment scrubbed (`KCA_SKIP_DOTENV=1`, `HOME=tmpdir`,
   `KCA_ALLOW_REMOTE` unset).

   - `test_tool_smoke_suite_runs_mocked` — full suite execution
     against the tmpdir DB; asserts ≥10 rows recorded.
   - `test_kaggle_replays_run_mocked` — each of the three
     Kaggle replays runs against fixtures; asserts metric keys
     present.
   - `test_kernel_dryrun_credentials_gate_refusal` — mirrors the
     M10-T007 refusal test under the M13 eval entry point.
   - `test_reasoning_deterministic_check_passes` — reasoning
     suite's deterministic check passes ≥80% of cases in
     `--route mocked` against the fixture responses.
   - `test_route_compare_refuses_without_allow_remote` — asserts
     the `REMOTE_NOT_APPROVED` refusal path BEFORE any case
     starts.
   - `test_report_aggregator_idempotent` — two `kca eval report
     --md` runs against the same run_id produce byte-identical
     output.

3. **`.github/workflows/eval.yml`**:
   - Trigger: `schedule: - cron: "30 3 * * *"` (03:30 UTC
     nightly) + `workflow_dispatch:` for manual runs.
   - Jobs:
     - `eval-mocked` — checkout, install kca, apply migrations
       to a containerised sqlite (no Supabase), run
       `kca eval run --all --route mocked --json --out
       /tmp/eval-snapshot.json`, run `kca eval report --md --out
       /tmp/eval-report.md`, upload both as workflow artefacts.
     - `eval-diff` — depends on `eval-mocked`; downloads the
       previous nightly's snapshot via `gh run download`,
       computes a side-by-side metric diff, posts a comment on
       the canonical "M13 nightly eval" tracking issue if any
       suite × route group flipped a `pass → fail` or
       `fail → pass`.
   - Permissions: `contents: read`, `issues: write` (for the
     diff comment), `actions: read`. No `KAGGLE_*` or `*_API_KEY`
     in the workflow env. The cron never reaches paid LLM
     routes — it is `--route mocked` always.
   - Network: defaults; the workflow does NOT need
     `dangerouslyDisableSandbox` because GitHub Actions is the
     sandbox boundary itself.

4. **Audit-grep regression sentinel** — the new workflow must
   not re-leak. Add a post-run grep step that fails the workflow
   if any line in the JSON snapshot or audit log mentions
   `kaggle competitions submit`, `kaggle kernels push`,
   `kaggle datasets create`, or `kaggle datasets version`.

5. **Schedule the diff tracking issue.** File one canonical
   GitHub issue: `M13 nightly eval — rolling diff`, labels
   `area:eval`, `area:ci`, `type:tracking`. The cron's
   `eval-diff` job comments on this issue (never opens a new one
   per nightly).

## Non-goals

- No paid LLM calls. The nightly cron is `--route mocked` always;
  paid routes are operator-triggered locally via T006.
- No real Kaggle calls. None.
- No CI for the UI (M13 does not touch `ui/`); the existing UI
  job in `test.yml` is unchanged.
- No alerting to Slack / email — the GitHub issue comment is the
  only notification channel.

## Acceptance criteria

- Issue #11 is CLOSED at run time — verified via
  `gh issue view 11 --json state`.
- `tests/test_m13_smoke.py` exists; ~6 tests; PASSes with
  `SUPABASE_DB_URL`; SKIPs cleanly without it.
- `tests/test_m13_e2e.py` exists; ~6 tests; PASSes with no DB /
  no creds / no net; total wall < 60 s.
- `pytest tests/test_m13_smoke.py tests/test_m13_e2e.py -v` PASS.
- `pytest tests/ services/decision_api/tests` — 0 regressions vs
  the T007 baseline.
- `.github/workflows/eval.yml` validates locally via
  `actionlint` (or equivalent); first manual `workflow_dispatch`
  run from a branch PR succeeds end-to-end.
- The audit-grep sentinel passes in the workflow.
- `M13 nightly eval — rolling diff` tracking issue exists.
- `ruff check .` + `ruff format --check .` clean.

## Permissions

- `git add` / `git commit` deferred to milestone closeout.
- `gh issue create` for the tracking issue — ALLOWED
  (non-destructive write).
- `gh workflow run` for manual smoke — ALLOWED.
- No Kaggle / LLM calls.

## Closeout format

```
M13-T008 closeout
  Issue #11 state at run time: CLOSED — verified via gh issue view 11
  New file: tests/test_m13_smoke.py (<n> tests, <s>s wall, DB-gated)
  New file: tests/test_m13_e2e.py (<n> tests, <s>s wall, no DB / no creds / no net)
  New file: .github/workflows/eval.yml (scheduled 03:30 UTC + workflow_dispatch)
  Tracking issue: <url> — "M13 nightly eval — rolling diff"
  Manual workflow_dispatch smoke run: <run_url> — passed
  pytest combined: <X> passed / <Y> skipped (0 regressions vs T007)
  Audit-grep guard: 0 lines matching forbidden Kaggle CLI commands
  ruff check + ruff format --check: clean
  Acceptance: PASS
  Next: M13-T009 (exit criteria + final review)
```

## Related issues

- M13 proposal issue.
- #11 — HARD PRE-REQ. Must be CLOSED before T008 runs.

## Stop condition

Stop after 60 turns. HALT and ask if:
- Issue #11 is OPEN at run time. The nightly cron must not
  re-introduce the dotenv leak; pause until #11 is closed.
- `actionlint` (or equivalent) flags a syntax issue with
  `eval.yml`. Fix in place before merging.
- The manual `workflow_dispatch` run fails for any reason other
  than environment differences (e.g. real network needed). The
  whole point is that the workflow runs offline.
- The audit-grep sentinel FAILs anywhere — investigate which
  subprocess reached the kaggle CLI and surface as a P0.
