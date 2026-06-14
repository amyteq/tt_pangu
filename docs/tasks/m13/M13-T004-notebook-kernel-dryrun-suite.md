# M13-T004: Notebook / kernel dry-run regression suite

## Milestone
M13: evaluation, reliability, and regression suite.

## Goal
Add an offline regression suite that exercises the M10 notebook /
kernel-push path under M10-T007's dry-run + audit-grep posture, as
a record-producing eval (not just a pytest). Reuses the existing
M10-T007 fixture (`tests/fixtures/tpu-getting-started/`) — does
NOT add a parallel fixture.

Cases covered: kg-nb round-trip, reviewer-gate firing, decision-API
approval round-trip, `kca kaggle push` credentials-gate refusal.
Metric: count of gates fired + the audit-grep sentinel result.
No real Kaggle, no real Anthropic, no real kernel push.

This task assumes **M13-T002 closeout is PASS** AND **M10-T007 is
merged on `main`** (the fixture and the gating code must already
exist).

## Read first

1. M13-T000, M13-T001, M13-T002 closeouts.
2. M10-T002, M10-T004, M10-T007 closeouts (the path being replayed).
3. `tests/test_m10_e2e.py` — the closest pattern; reuse the
   credentials-gate refusal block almost verbatim.
4. `tools/kca/kg.py::cmd_push` — the gate this suite asserts on.
5. `src/worker/reviewer.py` — the reviewer-gate stub the suite
   triggers.
6. `tests/fixtures/tpu-getting-started/` — DO NOT add a parallel
   fixture.
7. `tools/kca/eval/suites/tool_smoke/` (T002 driver shape).

## Scope

1. **Suite module** `tools/kca/eval/suites/kernel_dryrun/`:
   - Registers as `kernel-dryrun` v0.1.0, category
     `kernel_dryrun`.
   - Four cases, one per assertion (see scope step 2).
   - Reuses `tests/fixtures/tpu-getting-started/` (≤ ~5 MB; 2-class
     stub from M10-T007).

2. **Four cases.** Each emits one `eval_results` row:
   - `kg_nb_roundtrip` — convert the fixture notebook to
     percent-format `.py` and back; assert cell sequence and
     output equivalence (modulo execution timestamps). Metric:
     `cells_equal=True/False`, `latency_ms`.
   - `reviewer_gate_fires` — drive a stub worker that reaches
     `kernel_push`; assert exactly one `agent_reviews` row + one
     `human_decisions` row land with `target_op="kernel_push"`.
     Metric: `gates_fired=1`, `rows_created=2`, `latency_ms`.
   - `decision_api_approve_roundtrip` — POST approve to the
     decision_api (or `kca decisions approve`); assert state flip.
     Skipped cleanly if `SUPABASE_DB_URL` is unset (`status="skip"`).
     Metric: `approved=True`, `latency_ms`.
   - `credentials_gate_refusal` — subprocess invocation of
     `kca kaggle push --competition tpu-getting-started --notebook
     /dev/null --message "m13-eval dry-run — must refuse"` under
     a scrubbed env (`KCA_SKIP_DOTENV=1`, `HOME=tmpdir`); assert
     `payload["ok"]==False` AND `payload["error"]` contains
     `KAGGLE_USERNAME` or `KAGGLE_KEY`. Metric:
     `refused=True`, `payload_keys=[...]`, `latency_ms`.

3. **Audit-grep regression sentinel.** After the suite runs,
   assert `.agent/audit/tool-events.jsonl` (or equivalent) has 0
   lines whose command starts with `kaggle kernels push` or
   `kca kaggle push` for this suite's process — same guard as
   M10-T007, but recorded as a metric in the
   `credentials_gate_refusal` case (`audit_grep_clean=True`).

4. **No real Kaggle.** Inherit the M10-T007 stance: the test
   process must NEVER reach the real kaggle CLI. The suite asserts
   this is the case.

5. **Wire into `kca eval run`.** After T004:
   - `kca eval list --json` shows `kernel-dryrun` as a registered
     suite.
   - `kca eval run --suite kernel-dryrun --route mocked --dry-run
     --json` exits 0, creates one `eval_runs` row, inserts 4
     `eval_results` rows (with one expected `skip` if
     `SUPABASE_DB_URL` is unset).

## Non-goals

- No real Kaggle calls. None.
- No real `kaggle kernels push` — that is exactly the leak this
  suite guards against.
- No new fixtures — reuse M10-T007's.
- No extension of `tools/kca/kg.py::cmd_push`. If the gating code
  needs fixing, file a separate issue and pause this task.
- No LLM calls — `--route mocked` only.

## Acceptance criteria

- `tools/kca/eval/suites/kernel_dryrun/` registers as
  `kernel-dryrun`; `kca eval list` shows it.
- All four cases produce `eval_results` rows on a clean run; the
  `decision_api_approve_roundtrip` case may report `status="skip"`
  cleanly without `SUPABASE_DB_URL`.
- `credentials_gate_refusal` case has `refused=True` AND
  `audit_grep_clean=True`.
- Audit-grep guard PASSes: 0 lines for `kaggle kernels push` /
  `kca kaggle push` from the suite's subprocesses.
- Two consecutive runs produce identical `metrics` per case
  (modulo `latency_ms`).
- `ruff check .` + `ruff format --check .` clean.
- `pytest tests/ services/decision_api/tests` — 0 regressions vs
  T003 baseline.

## Permissions

- `git add` / `git commit` deferred to milestone closeout.
- LOCAL_WRITE Supabase — ALLOWED.
- No real Kaggle calls.
- No real LLM calls.

## Closeout format

```
M13-T004 closeout
  Suite: tools/kca/eval/suites/kernel_dryrun/ (registered as `kernel-dryrun` v0.1.0)
  Cases: 4 (kg_nb_roundtrip, reviewer_gate_fires, decision_api_approve_roundtrip, credentials_gate_refusal)
  Fixture reuse: tests/fixtures/tpu-getting-started/ (no parallel fixture added)
  eval_runs row id: <uuid>
  eval_results rows: 4 (pass / skip / fail / error counts)
  credentials_gate_refusal: refused=True, audit_grep_clean=True
  Audit-grep guard: 0 lines matching forbidden Kaggle CLI commands
  Determinism check: 2 consecutive runs — same metrics per case: YES
  pytest: <X> passed / <Y> skipped (0 regressions)
  ruff check + ruff format --check: clean
  Acceptance: PASS
  Next: M13-T005 (reasoning-heavy benchmark)
```

## Related issues

- M13 proposal issue.
- #11 (dotenv leak) — should still be CLOSED at run time. If
  reopened, halt and surface.

## Stop condition

Stop after 80 turns. HALT and ask if:
- The audit-grep sentinel FAILs at any point — that is exactly
  the regression this suite is designed to catch. Investigate
  which subprocess reached the kaggle CLI and file as a P0.
- `tests/fixtures/tpu-getting-started/` is missing or empty.
  M10-T007 must have landed first; if it has not, this task is
  blocked.
- Two runs produce divergent metrics in a way that suggests
  hidden state (often: leftover audit log lines from a previous
  run; ensure the tmpdir is fresh).
