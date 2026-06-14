# M13-T007: Metrics aggregator + `kca eval report` (JSON + Markdown)

## Milestone
M13: evaluation, reliability, and regression suite.

## Goal
Implement `kca eval report --json` and `kca eval report --md`.
The report rolls up rows from `eval_results` for a given
`eval_run_id` (or the latest by default), groups by
`(suite, route)`, and emits a single JSON document AND a single
Markdown table. The Markdown is human-diffable: stable row order,
fixed-point metric formatting, no environment-dependent strings.

No new tables; T007 reads `eval_results` and writes a snapshot
file under `runs/m13-eval/<timestamp>/report.{json,md}`.

This task assumes **M13-T006 closeout is PASS** so the harness
emits real (or mocked) rows for the aggregator to roll up.

## Read first

1. M13-T001 closeout (`eval_results` schema).
2. M13-T002 through M13-T006 closeouts (the rows the report rolls
   up).
3. `tools/kca/run.py` (run-artifact layout precedent —
   `runs/<comp>/<run_id>/`).
4. `docs/milestones/m9/final-review.md`, `docs/milestones/m10/final-review.md` (visual
   precedent for the Markdown layout).
5. `docs/architecture/eval-regression-suite.md` (report-shape
   contract from ADR-0019).
6. Existing `kca run list --json` output (rolling-up pattern).

## Scope

1. **Aggregator module** `tools/kca/eval/report.py`:
   - `summarize_run(run_id) -> ReportPayload` — pure function
     over DB rows; no I/O.
   - `ReportPayload` shape:
     ```jsonc
     {
       "run_id": "<uuid>",
       "started_at": "<iso8601>",
       "finished_at": "<iso8601 | null>",
       "totals": {"pass": <n>, "fail": <n>, "skip": <n>, "error": <n>},
       "cost_usd": <num>,
       "aborted_on_budget": <bool>,
       "groups": [
         {
           "suite": "<name>",
           "route": "<route>",
           "case_count": <n>,
           "pass_count": <n>,
           "metrics_aggregate": {
             "<key>": {"mean": <num>, "min": <num>, "max": <num>, "p50": <num>}
           },
           "cases": [
             {"name": "<case>", "status": "<s>", "metrics": {…}, "latency_ms": <n>, "cost_usd": <c>}
           ]
         }
       ]
     }
     ```

2. **CLI verb fill-in.**
   - `kca eval report [<run_id>] [--json | --md] [--out PATH]`.
   - With no `run_id`, defaults to the latest by `started_at desc`.
   - `--json` emits the `ReportPayload` JSON to stdout (or
     `--out`).
   - `--md` emits a Markdown report with the layout below to
     stdout (or `--out`).
   - Default behaviour (neither `--json` nor `--md`): write
     both files under `runs/m13-eval/<timestamp>/report.{json,md}`
     and print the directory path.

3. **Markdown layout** — must diff cleanly across runs:
   ```markdown
   # M13 eval report — <run_id>
   _started <iso8601>; finished <iso8601 | running>; cost $<c>;
    aborted_on_budget=<bool>_

   ## Totals
   | status | count |
   |---|---|
   | pass | <n> |
   | fail | <n> |
   | skip | <n> |
   | error | <n> |

   ## By suite × route
   | suite | route | cases | pass | metric_keys | latency_ms_p50 | cost_usd |
   |---|---|---|---|---|---|---|
   | tool-smoke | mocked | <n> | <n> | <comma-list> | <n> | <c> |
   …

   ## Per-case detail
   <one collapsible <details> block per (suite, route) with case rows>
   ```

4. **Stable ordering.** Suites listed in registration order
   (matches `eval_suites.created_at`). Routes listed in the
   ADR-0019 canonical order (`mocked`, `local_vllm`,
   `claude_haiku_4_5`, `claude_sonnet_4_6`, `gpt_4o`). Cases
   listed in `cases.yaml` order (i.e. `eval_results.created_at`).

5. **Fixed-point formatting.** Floats: `f"{x:.4f}"` (4 sig digits
   for accuracies / RMSLE; 2 for cost USD). Wall times:
   integer ms. No locale-dependent thousand-separators.

6. **No new top-level CLI subcommands.** The verb already exists
   from T001's scaffold — T007 fills its body.

## Non-goals

- No new tables.
- No live LLM calls.
- No real Kaggle calls.
- No HTML report — the Markdown is the human-readable artefact
  for now; HTML is a follow-up if anyone asks for it.
- No publishing to GitHub Pages or any external surface — the
  report lives under `runs/m13-eval/`.

## Acceptance criteria

- `tools/kca/eval/report.py` exists with `summarize_run` as a
  pure function over DB rows; mocked DB tests pass.
- `kca eval report --json` against a known run produces a
  parseable `ReportPayload` JSON.
- `kca eval report --md` against the same run produces a
  Markdown document matching the layout above; two consecutive
  runs of `--md` against the same `run_id` produce byte-identical
  output.
- Default `kca eval report` (no flag) writes both files under
  `runs/m13-eval/<timestamp>/report.{json,md}` and prints the
  path.
- `runs/m13-eval/` is committed for the M13 PR (small text
  files only); raw data does not leak in.
- `ruff check .` + `ruff format --check .` clean.
- `pytest tests/ services/decision_api/tests` — 0 regressions.

## Permissions

- `git add` / `git commit` deferred to milestone closeout.
- LOCAL_WRITE — ALLOWED (the report files).
- LOCAL_READ Supabase — ALLOWED.
- No Kaggle / LLM calls.

## Closeout format

```
M13-T007 closeout
  Aggregator: tools/kca/eval/report.py (summarize_run pure-fn; <n> tests pass mocked)
  CLI: kca eval report --json | --md | (default both); --out honoured
  Sample report run: <run_id>
    JSON: runs/m13-eval/<timestamp>/report.json (<size> KB)
    MD: runs/m13-eval/<timestamp>/report.md (<size> KB; <l> lines)
  Determinism: 2 consecutive --md runs against same run_id — byte-identical: YES
  Stable ordering verified: suites in registration order; routes in canonical enum order
  Audit-grep guard: 0 lines matching forbidden Kaggle CLI commands
  pytest: <X> passed / <Y> skipped (0 regressions)
  ruff check + ruff format --check: clean
  Acceptance: PASS
  Next: M13-T008 (CI nightly cron + smoke / e2e tests)
```

## Related issues

- M13 proposal issue.

## Stop condition

Stop after 80 turns. HALT and ask if:
- The MD report cannot be made byte-deterministic for a given
  `run_id`. Identify the source of drift (often: dict ordering,
  timestamps in row order) and fix the ordering.
- The aggregator needs a new DB query that isn't expressible via
  the T001 helpers. Add a new helper to `tools/kca/db.py` rather
  than reaching across modules.
- The `runs/m13-eval/<timestamp>/` directory leaks something
  larger than ~50 KB. Investigate; the report should be small
  and text-only.
