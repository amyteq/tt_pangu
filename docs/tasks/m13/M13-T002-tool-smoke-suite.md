# M13-T002: Tool-smoke suite (deterministic; no LLM; ≥10 cases)

## Milestone
M13: evaluation, reliability, and regression suite.

## Goal
Author the first concrete eval suite — a deterministic tool-smoke
suite that exercises the existing tool registry (`src/worker/tools.py`
+ `.kca/tools/tools.yaml`) with fixed inputs and expected outputs.
No LLM, no Kaggle network, no Anthropic/OpenAI calls. Coverage
target: every tool flagged `category=read_only` in `tools.yaml`,
plus the four most-used `local_write` tools.

This task assumes **M13-T001 closeout is PASS** — the scaffold,
helpers, and migration are in place.

## Read first

1. M13-T000, M13-T001 closeouts.
2. `src/worker/tools.py` — the tool registry the suite evaluates.
3. `.kca/tools/tools.yaml` — tool metadata (category, side-effect
   level, schema).
4. `src/worker/tool_executor.py` — the executor the suite calls
   into.
5. `tests/test_m7_smoke.py` — already exercises some tools;
   reuse the fixture-input shape where possible.
6. `tools/kca/eval/__init__.py` (the T001 scaffold).
7. `docs/architecture/eval-regression-suite.md` (per-suite metric
   contract).

## Scope

1. **Author suite module** `tools/kca/eval/suites/tool_smoke/`:
   - `__init__.py` exports `register(db)` (calls
     `db.register_eval_suite(name="tool-smoke", category="tool_smoke",
     version="0.1.0", …)`) and a `cases()` generator.
   - `cases.yaml` (or `cases.py` if richer) declares each case:
     `{name, tool, input_json, expected_output_subset, expected_status}`.
   - The runner module reads each case, calls `tool_executor.run(tool,
     input_json)`, compares against `expected_output_subset`
     (subset-match, not full equality), records latency + status into
     `eval_results` via the T001 helpers.

2. **Coverage target** — ≥10 cases:
   - Every `category=read_only` tool in `tools.yaml` exercised by
     at least one case (today: `read_file`, `list_dir`, `kca_run_list`,
     `kca_competition_info`, `kca_kaggle_list`, etc. — verify against
     current `tools.yaml`).
   - At least four `category=local_write` cases, one each for:
     `kca_run_init`, `kca_run_record_metric`, `kca_research_add`,
     and one `write_file` case scoped to a tmpdir.
   - Zero `category=remote_write` cases — those are out of scope
     for tool-smoke (see T004 / T006 for indirect coverage).

3. **Determinism guard.** Every case must run in < 5 s wall and emit
   the same `metrics` JSON on repeated runs against a clean tmpdir.
   The suite seeds `random.seed(0)` and uses tmpdir fixtures from
   `tests/fixtures/tool_smoke/`.

4. **Metric contract.** Per case, the suite emits the following
   keys into `eval_results.metrics`:
   - `latency_ms` (int)
   - `output_match` (bool) — subset-match against expected
   - `output_keys` (list[str]) — sorted keys actually emitted
   - `status` ∈ `{pass, fail, skip, error}` (also the row's `status`
     column)

5. **Audit-grep guard.** Inherit the M10-T007 sentinel: 0 lines
   matching `kaggle competitions submit`, `kaggle kernels push`,
   `kaggle datasets create`, `kaggle datasets version` reach the
   kaggle CLI from any suite process. Verify by intercepting the
   audit log under `.agent/audit/` after the suite runs.

6. **Wire into `kca eval run`.** After T002, `kca eval run --suite
   tool-smoke --route mocked --dry-run --json` should:
   - Create an `eval_runs` row (`dry_run=true`, `route="mocked"`).
   - Insert ≥10 `eval_results` rows.
   - Finish with `total_pass + total_skip + total_fail == total_cases`.

## Non-goals

- No LLM calls — `mocked` route only.
- No Kaggle network. No real submission anything.
- No new tools added — this task evaluates the existing registry.
- No coverage of `remote_write` tools — kept for T004 (notebook /
  kernel dry-run) and T006 (model-route comparison).
- No report aggregator — that lands in T007.

## Acceptance criteria

- `tools/kca/eval/suites/tool_smoke/` exists with ≥10 cases.
- `kca eval list --json` shows `tool-smoke` as a registered suite.
- `kca eval run --suite tool-smoke --route mocked --dry-run --json`
  exits 0, creates one `eval_runs` row and ≥10 `eval_results` rows.
- Two consecutive runs produce identical `metrics` JSON per case
  (modulo `latency_ms` which is bounded but not byte-equal).
- Audit-grep guard PASSes: 0 lines for the four forbidden Kaggle
  CLI invocations from the suite process.
- `ruff check .` + `ruff format --check .` clean.
- `pytest tests/ services/decision_api/tests` — 0 regressions vs
  T001 baseline.

## Permissions

- `git add` / `git commit` deferred to milestone closeout.
- LOCAL_WRITE Supabase — ALLOWED.
- No Kaggle / LLM calls.

## Closeout format

```
M13-T002 closeout
  Suite: tools/kca/eval/suites/tool_smoke/ (registered as `tool-smoke` v0.1.0)
  Cases: <N> (read_only: <r>, local_write: <l>; total wall <s>s)
  eval_runs row id: <uuid>
  eval_results rows: <N> (pass: <p>, skip: <s>, fail: <f>, error: <e>)
  Determinism check: 2 consecutive runs — same metrics JSON: YES
  Audit-grep guard: 0 lines matching forbidden Kaggle CLI commands
  pytest: <X> passed / <Y> skipped (was <X> / <Y>; 0 regressions)
  ruff check + ruff format --check: clean
  Acceptance: PASS — first concrete suite landed
  Next: M13-T003 (Kaggle classic-practice replay)
```

## Related issues

- M13 proposal issue.

## Stop condition

Stop after 80 turns. HALT and ask if:
- A tool flagged `read_only` produces non-deterministic output for
  identical input (would be a tool-registry bug; file as a follow-up).
- The audit-grep guard FAILs — that is exactly the leak this suite
  is supposed to detect. Investigate which tool reached the kaggle
  CLI and surface as a P0 issue.
- The `mocked` route's behaviour drifts from T001's scaffold. Loop
  back to T001 if the drift is structural.
