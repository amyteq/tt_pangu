# M13-T005: Reasoning-heavy benchmark (5–10 fixed prompts; deterministic + rubric)

## Milestone
M13: evaluation, reliability, and regression suite.

## Goal
Author a reasoning-heavy benchmark suite covering 5–10 fixed
prompts that exercise the worker / skill stack on tasks where
deterministic ground truth is checkable: research-brief from
cached pages, debug-a-worker-trace from a canned event slice,
CV-result analysis from a frozen `experiment_runs` row,
"should we submit?" decision-gate rationale.

Two judges per prompt:
- a **deterministic check** (regex / JSON shape / required-keys
  match) that pass/fails the case without an LLM call.
- an **optional rubric-LLM judge** gated behind `--route` (cheap
  route only — default `claude_haiku_4_5`); hard $0.05/prompt cap.

This task assumes **M13-T002 closeout is PASS**. T006 (route
comparison) consumes this suite later.

## Read first

1. M13-T000, M13-T001, M13-T002 closeouts.
2. `src/worker/worker.py` (the agent loop the benchmark drives).
3. `src/worker/routing.py` (per-job-type routing).
4. `tools/kca/research_fetch.py` (cached pages are the input to
   one of the prompts).
5. `docs/tasks/m5/M5-T002-browser-fetch-tool.md` (research-brief precedent).
6. `.claude/skills/research-brief/SKILL.md` (the skill one prompt
   evaluates against).
7. `docs/architecture/eval-regression-suite.md` (metric contract).
8. `tools/kca/eval/suites/tool_smoke/` (T002 driver shape).

## Scope

1. **Suite module** `tools/kca/eval/suites/reasoning/`:
   - Registers as `reasoning` v0.1.0, category `reasoning`.
   - 5–10 cases under `cases.yaml`. Each declares:
     `{name, prompt_file, input_files, deterministic_check,
     rubric_prompt, expected_keys, max_cost_usd}`.

2. **Five canonical prompts** (the recommended seed set; more is
   fine):
   - `research_brief_from_cached_pages` — three cached HTML pages
     under `tests/fixtures/research/`; expected output: a brief
     with citations, trust labels, and an `explicit_unknowns`
     list. Deterministic check: required keys + citation count
     ≥ 3 + trust label ∈ enum.
   - `debug_worker_trace` — a frozen `agent_job_events` slice
     (JSONL) under `tests/fixtures/reasoning/worker_trace.jsonl`;
     expected output: a JSON diagnosis with `root_cause`,
     `evidence_event_ids` (≥1), `proposed_fix`. Deterministic
     check: required keys + at least one valid event id.
   - `cv_result_analysis` — a frozen `experiment_runs` row
     (JSON) under `tests/fixtures/reasoning/cv_row.json`;
     expected output: `{is_overfit, recommendation, next_experiment}`
     with `recommendation` ∈ enum. Deterministic check: enum
     match.
   - `submit_decision_rationale` — input: M9-style `submissions`
     candidate row + current best LB; expected output:
     `{should_submit, confidence, rationale}` matching the
     four-scenario decision table in `CLAUDE.md` §KCA autonomous
     submission strategy. Deterministic check: scenario tag in
     `{1,2,3,4}` + boolean shape.
   - `tool_choice_rationale` — input: a stubbed agent step where
     the model must pick between two `kca` subcommands; expected
     output: `{chosen_tool, justification}`. Deterministic check:
     `chosen_tool` ∈ the legal subcommand list.

3. **Deterministic vs rubric.** Each case records both:
   - `deterministic_pass` (bool) — from the regex / shape check.
   - `rubric_score` (float [0,1] or null) — from the optional
     rubric-LLM call. Null when `--route mocked` (the default).

4. **Cost cap.** When a non-mocked route is selected, the suite
   enforces `max_cost_usd` per case (default $0.05) AND a per-run
   budget (passed via `--budget`). If a case would exceed, mark it
   `status="skip"` with `error_text="BUDGET_EXCEEDED"`.

5. **Determinism.** `--route mocked` runs are byte-deterministic
   (the mocked LLM returns a fixture string per prompt; see
   `tests/fixtures/reasoning/mocked_responses.json`). Non-mocked
   runs are not byte-deterministic but must be value-bounded
   (`rubric_score ∈ [0,1]`).

6. **Wire into `kca eval run`.** After T005:
   - `kca eval list --json` shows `reasoning` as a registered
     suite.
   - `kca eval run --suite reasoning --route mocked --dry-run
     --json` exits 0 and creates one `eval_runs` row + 5–10
     `eval_results` rows.

## Non-goals

- No real LLM calls in this task (T006 wires up real routes
  across suites — the budget cap and `--route` flag are
  scaffolded here but not exercised live).
- No new benchmark prompts beyond the five canonical seeds — keep
  the suite small and surgical.
- No new tables — emit metrics into `eval_results.metrics_jsonb`.

## Acceptance criteria

- `tools/kca/eval/suites/reasoning/` registers as `reasoning`;
  `kca eval list` shows it.
- 5–10 cases under `cases.yaml`; each carries
  `deterministic_check` and (optional) `rubric_prompt`.
- `kca eval run --suite reasoning --route mocked --dry-run --json`
  exits 0, produces 5–10 `eval_results` rows.
- For every case, `deterministic_pass` is set; `rubric_score` is
  null in `--route mocked` mode.
- Two consecutive `--route mocked` runs produce byte-identical
  `metrics` JSON per case.
- Audit-grep guard PASSes: 0 lines for the four forbidden Kaggle
  CLI commands.
- `ruff check .` + `ruff format --check .` clean.
- `pytest tests/ services/decision_api/tests` — 0 regressions.

## Permissions

- `git add` / `git commit` deferred to milestone closeout.
- LOCAL_WRITE Supabase — ALLOWED.
- No real Kaggle calls.
- No real LLM calls in T005 — wiring only.

## Closeout format

```
M13-T005 closeout
  Suite: tools/kca/eval/suites/reasoning/ (registered as `reasoning` v0.1.0)
  Cases: <N> (research_brief_from_cached_pages, debug_worker_trace, cv_result_analysis, submit_decision_rationale, tool_choice_rationale, [optional extras])
  Fixtures: tests/fixtures/reasoning/* + tests/fixtures/research/* (total <s> KB)
  Deterministic checks pass rate (--route mocked): <p>/<N>
  Rubric judge: null (route=mocked, by design)
  Determinism check: 2 consecutive runs — byte-identical metrics: YES
  Audit-grep guard: 0 lines matching forbidden Kaggle CLI commands
  pytest: <X> passed / <Y> skipped (0 regressions)
  ruff check + ruff format --check: clean
  Acceptance: PASS
  Next: M13-T006 (model-route comparison harness)
```

## Related issues

- M13 proposal issue.

## Stop condition

Stop after 80 turns. HALT and ask if:
- A canonical prompt's deterministic check is brittle (e.g. fails
  on benign formatting differences). Re-design the check before
  expanding the prompt count.
- A fixture under `tests/fixtures/reasoning/` exceeds ~1 MB.
  Sub-sample more aggressively.
- The mocked-response fixture cannot satisfy every case's
  deterministic check. Surface — a prompt that can't pass even on
  the mocked response is mis-designed.
