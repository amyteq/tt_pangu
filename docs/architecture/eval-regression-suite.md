# Eval regression-suite architecture

Status: M13 (2026-06-09). Companion to
[`ADR-0019`](../adr/0019-eval-regression-suite.md). T000 lands this
doc; T001 lands migration 0010 + the `kca eval` CLI scaffold;
T002–T007 fill the individual suites; T008 wires the nightly cron;
T009 is the milestone close.

## Goals (recap)

Make every change on `main` measurable against a fixed, checked-in
set of suites. Produce a JSON + Markdown snapshot per `eval run` that
is diffable in a PR. Never call real Kaggle from a suite; only T006
may call a real LLM, and only under an explicit budget cap.

## ASCII data-flow

```
                                           +---------------------------+
                                           |  tests/fixtures/<slug>/    |
                                           |  (checked-in, <=5 MB each) |
                                           +-------------+-------------+
                                                         |
                                                         | read-only
                                                         v
+-----------------+    register()     +------------------+-----------------+
|  tools/kca/eval | <---------------- |  tools/kca/eval/suites/<slug>/    |
|     /__init__.py|                   |  (Python module)                  |
|  suite registry |                   |    register() -> SuiteSpec        |
+--------+--------+                   |    run(case, route) -> EvalResult |
         |                            +------------------+-----------------+
         | iterate                                       |
         v                                               | one call per (case x route)
+-----------------+                                      v
| kca eval run    |                            +-------------------+
|   --suite <s>   |                            |  Route layer      |
|   --route <r>   |  --route mocked (default)  |  src/worker/      |
|   --json        +--------------------------> |     routing.py    |
|   --dry-run     |  --route claude_*/gpt_*/   |                   |
+--------+--------+   local_vllm (T006 only)   +---------+---------+
         |                                               |
         | per-invocation external_llm gate              | model_for(...)
         | (only if route is paid)                       | or mock_completion
         v                                               v
+-----------------+                                +-----------------+
| Approval gate   |                                | LiteLLM         |
| (human_decisions|                                | (real OR mocked)|
|   row)          |                                +-----------------+
+--------+--------+
         |
         v
+--------+--------+                +---------------------------+
| Harness loop    |                |  Audit-grep sentinel       |
| - seeds RNG     |--->[ verify ]->|  inherited from M10-T007:  |
| - dispatches    |                |  0 lines for               |
| - tracks cost   |                |    `kaggle competitions    |
| - checks budget |                |       submit`,             |
|     cap         |                |    `kaggle kernels push`,  |
| - writes rows   |                |    `kaggle datasets create`|
+--------+--------+                |  reach the kaggle CLI from |
         |                         |  any suite process.        |
         |                         +---------------------------+
         v
+--------+---------+    +-----------------+   +------------------+
| eval_runs (1 row)|<---| eval_results    |-->| eval_suites      |
+------------------+    | (N rows: case x |   | (registry; slow- |
                        |  route)         |   |  changing)       |
                        +--------+--------+   +------------------+
                                 |
                                 | aggregate
                                 v
                       +------------------+
                       | kca eval report  |
                       |   --json         |
                       |   --md           |
                       +--------+---------+
                                |
                                v
        +-----------------------+-----------------------+
        |  runs/m13-eval/<ts>/report.json               |
        |  runs/m13-eval/<ts>/report.md                 |
        |  (mirrors ADR-0008 run-artifact layout;        |
        |   committed to the M13 PR for posterity.)     |
        +-----------------------------------------------+
```

The mocked route is the default in every path that does not set
`KCA_ALLOW_REMOTE=1`, including the nightly cron at T008.

## Per-table layout

Migration 0010 lands these three tables. The columns below are the
ADR-0019 commitment; column nullability and FK lines are the
to-be-enforced shape for T001's migration to honour byte-for-byte.

### `eval_suites` — registry of registered suites

| Column | Type | Nullable | FK | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | PK | `gen_random_uuid()` default. |
| `slug` | `text` | NO | unique | `tool_smoke`, `kaggle_replay_titanic`, `kernel_dryrun`, `reasoning`, `router_compare`. |
| `display_name` | `text` | NO | | Human-friendly label for the report. |
| `category` | `text` | NO | | One of `tool`, `kaggle_replay`, `kernel_dryrun`, `reasoning`, `router_compare`. |
| `default_route` | `text` | NO | | Usually `mocked`. The suite's reference route. |
| `requires_db` | `boolean` | NO | | If TRUE, suite skips when `SUPABASE_DB_URL` is unset. |
| `requires_remote` | `boolean` | NO | | If TRUE, suite skips when `KCA_ALLOW_REMOTE != 1`. |
| `description` | `text` | YES | | One paragraph. |
| `created_at` | `timestamptz` | NO | | `now()` default. |

Indexes: `(slug)` unique.

### `eval_runs` — one row per `kca eval run` invocation

| Column | Type | Nullable | FK | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | PK | `gen_random_uuid()` default. |
| `project_id` | `uuid` | YES | `projects.id` | Nullable for synthetic CI runs that have no human-owned project. |
| `started_at` | `timestamptz` | NO | | `now()` default. |
| `ended_at` | `timestamptz` | YES | | Set on terminal status. |
| `git_sha` | `text` | YES | | Resolved at run start. |
| `route_summary` | `text` | NO | | Comma-separated list of routes used in the run (e.g. `mocked,claude_haiku_4_5`). |
| `kca_dry_run` | `boolean` | NO | | Mirrors the `--dry-run` flag. |
| `budget_cap_usd` | `numeric(10,4)` | YES | | Approved cap; NULL when no paid route is involved. |
| `budget_spent_usd` | `numeric(10,4)` | NO | | Running total; updated as cases complete. Default `0`. |
| `status` | `text` | NO | | `running` / `ok` / `aborted_on_budget` / `aborted_on_error`. |
| `notes` | `text` | YES | | Human-supplied free-form (PR ref, comparison anchor, …). |

Indexes: `(started_at DESC)`, `(project_id, started_at DESC)`.

### `eval_results` — one row per (case x route) under a run

| Column | Type | Nullable | FK | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | PK | `gen_random_uuid()` default. |
| `eval_run_id` | `uuid` | NO | `eval_runs.id` ON DELETE CASCADE | Owning run. |
| `suite_id` | `uuid` | NO | `eval_suites.id` ON DELETE RESTRICT | Which suite produced this row. |
| `case_slug` | `text` | NO | | Per-suite case identifier (e.g. `add_two_numbers`, `titanic_baseline_lr`). |
| `route` | `text` | NO | | The route used; cross-referenced with `MODEL_ROUTES` keys or model ids. |
| `status` | `text` | NO | | `ok` / `failed` / `skipped` / `aborted`. |
| `latency_ms` | `integer` | YES | | Per-case wall time. NULL if `skipped`. |
| `cost_usd` | `numeric(10,4)` | NO | | Default `0`. Real value only for paid routes. |
| `metrics_jsonb` | `jsonb` | NO | | Per-suite metric bag (keys defined below). |
| `context_jsonb` | `jsonb` | NO | | Seed, route fixture id, case fixture path; used to reproduce a row. |
| `error_message` | `text` | YES | | Set when `status = failed`. |
| `created_at` | `timestamptz` | NO | | `now()` default. |

Indexes: `(eval_run_id, suite_id, route)`, `(suite_id, case_slug)`,
`(created_at DESC)`.

## Per-suite metric definitions

Each suite emits a documented schema into `eval_results.metrics_jsonb`.
The harness does NOT validate the schema — that is the suite author's
discipline. The report aggregator (T007) groups by `suite × route`
and renders only the metric keys it recognises for each suite.

### `tool_smoke` (T002)

| Key | Type | Meaning |
|---|---|---|
| `exit_code` | int | Tool exit code (0 on success). |
| `stdout_sha256` | string | SHA-256 of the captured stdout; deterministic per case. |
| `stderr_sha256` | string | SHA-256 of the captured stderr; deterministic per case. |
| `bytes_written` | int | For `LOCAL_WRITE` tools, total bytes written to the sandbox tmpdir. |
| `matched_expected` | boolean | Whether the case's deterministic expected-output assertion held. |

### `kaggle_replay_*` (T003)

One suite per competition slug — `kaggle_replay_titanic`,
`kaggle_replay_spaceship_titanic`, `kaggle_replay_house_prices`.

| Key | Type | Meaning |
|---|---|---|
| `cv_score` | float | Cross-validation score (accuracy for classification, RMSLE for regression). |
| `cv_metric` | string | The score's metric name (`accuracy`, `rmsle`, `auc`). |
| `cv_n_splits` | int | Number of CV folds. |
| `fit_seconds` | float | Wall time for the baseline fit. |
| `rows_in_fixture` | int | Number of rows in the frozen sub-sample. |
| `baseline_id` | string | Identifier for the baseline (e.g. `m9_lr`, `m9_hgb_fe`, `m5_xgb`). |

### `kernel_dryrun` (T004)

Reuses M10-T007 fixtures (`tests/fixtures/tpu-getting-started/`).

| Key | Type | Meaning |
|---|---|---|
| `gates_fired` | int | Number of approval gates the dry-run flow exercised. |
| `reviewer_decision` | string | `approve` / `request_changes` / `block` / `none`. |
| `credentials_gate_refusal` | boolean | Whether the missing-credentials path correctly refused before the kaggle CLI. |
| `audit_grep_violations` | int | MUST be 0. Number of lines in the suite's audit log matching the M10-T007 deny patterns. |
| `kernel_metadata_valid` | boolean | Whether the generated kernel-metadata.json passes shape validation. |

### `reasoning` (T005)

| Key | Type | Meaning |
|---|---|---|
| `deterministic_judge_pass` | boolean | Regex / JSON-shape / key-facts assertion result. |
| `rubric_score` | float | 0.0–1.0, only set when an LLM rubric judge ran. |
| `rubric_judge_route` | string | Route used for the rubric (always `claude_haiku_4_5` per T005 spec). |
| `rubric_cost_usd` | float | Per-prompt cost; capped at $0.05 per T005 spec. |
| `prompt_id` | string | Fixed prompt identifier. |

### `router_compare` (T006)

| Key | Type | Meaning |
|---|---|---|
| `parent_suite` | string | Which T002–T005 sub-suite this row corresponds to. |
| `parent_case_slug` | string | Case slug from the parent suite. |
| `route_cost_usd` | float | Per-route cost for the same case. |
| `route_latency_ms` | int | Per-route latency. |
| `route_status` | string | `ok` / `aborted_on_budget` / `failed`. |
| `route_metric_value` | float | The route-comparable metric (e.g. CV score, rubric score). |

## Route secrets map

Where each route reads its secret, and which routes need
`KCA_ALLOW_REMOTE=1`.

| Route key | Resolves to | Secret read from | Needs `KCA_ALLOW_REMOTE=1` |
|---|---|---|---|
| `mocked` | `litellm.mock_completion` with per-suite fixture string | (none) | NO |
| `local_vllm` | `src/worker/local_model.pick_endpoint()` | `KCA_LOCAL_ENDPOINT_*` env vars | NO |
| `claude_sonnet_4_6` / `implement` / `experiment` | `claude-sonnet-4-6` via LiteLLM | `ANTHROPIC_API_KEY` | YES |
| `claude_haiku_4_5` / `research` | `claude-haiku-4-5` via LiteLLM | `ANTHROPIC_API_KEY` | YES |
| `claude_opus_4_7` / `eval` / `analysis` / `review` | `claude-opus-4-7` via LiteLLM | `ANTHROPIC_API_KEY` | YES |
| `gpt_4o` | `gpt-4o` via LiteLLM | `OPENAI_API_KEY` | YES |
| `log_triage` / `summarise` | local sentinel → `local_vllm` or fallback | `KCA_LOCAL_ENDPOINT_*` | NO (the fallback is itself a local route) |

The harness reads secrets only via the existing
`src/worker/routing.py` and LiteLLM provider layer; the eval module
itself never opens `.env*` files. This preserves the dev-phase
secret policy: the harness is a normal LiteLLM caller, no different
from the worker.

## Audit-grep sentinel inheritance

Every M13 suite MUST inherit the M10-T007 audit-grep guard:

> 0 lines for `kaggle competitions submit`, `kaggle kernels push`,
> `kaggle datasets create`, `kaggle datasets version` reach the
> kaggle CLI from any suite process.

Mechanism (delegated to T002–T008):

- The harness wraps each `run(case, route)` invocation with a
  per-process audit logger; lines are written to
  `runs/m13-eval/<ts>/audit/<suite>/<case>.log`.
- After the run completes, the harness greps that directory for the
  deny patterns. Any non-zero hit aborts the run with
  `status = aborted_on_error` on the `eval_runs` row, sets
  `eval_results.metrics_jsonb.audit_grep_violations` for the
  offending case, and surfaces the leak path in the JSON / Markdown
  report.
- The CI nightly cron (T008) treats any audit-grep violation as a
  hard CI failure regardless of the per-suite status.

The audit-grep guard is the same shape as M10-T007's per-test guard
— it is intentionally not generalised into a hook (hook-based
enforcement is a deferred follow-up per `discovery-debate-gate.md`
§"Non-enforcement"). The eval-time guard is a defence-in-depth layer
on top of the regular `gh kg push` / `gh kg submit` approval gates.

## Run-artifact layout

Mirrors `tools/kca/run.py`'s `runs/<comp>/<run_id>/` precedent.

```
runs/
  m13-eval/
    20260609_184500_<short-sha>/
      meta.json         # eval_run_id, started_at, git_sha, route_summary
      report.json       # the T007 aggregator's JSON snapshot
      report.md         # the T007 aggregator's Markdown table
      audit/
        tool_smoke/
          add_two_numbers.log
          ...
        kaggle_replay_titanic/
          titanic_baseline_lr.log
          ...
```

`report.md` is committed to the M13 closing PR for posterity (so the
first M13 baseline ships with a baselined snapshot, per the M13
loop-prompts "Required tests / evidence" section).

## CLI surface

```
kca eval list                   # list registered suites
kca eval run                    # run one or more suites; --all to run every suite
  [--suite <slug> ...]
  [--route <key>]               # default: mocked
  [--budget-cap-usd <n>]        # required for any non-mocked / non-local route
  [--dry-run]
  [--json]
kca eval show --run-id <uuid>   # detailed view of one run's results
kca eval report                 # roll up the latest (or named) run
  [--run-id <uuid>]
  [--md|--json]
  [--out <path>]                # default: runs/m13-eval/<ts>/
```

The four verbs (`list` / `run` / `show` / `report`) are pinned by
this architecture doc; T001 lands them as scaffold (each returns a
machine-readable JSON envelope; `run` refuses with
`NO_SUITES_REGISTERED` until T002+ register suites).

## Cross-references

- ADR-0019 — the decision record this architecture realises.
- ADR-0006 (approval gates) — `external_llm` gate plumbing.
- ADR-0008 (artifact storage local-first) — `runs/m13-eval/<ts>/`
  layout precedent.
- ADR-0010 (per-job-type model routing) — `--route` source of truth.
- ADR-0013 (multi-exporter OTEL) — pattern the T007 report borrows
  if a future revision needs SQLite mirroring.
- M10-T007 — audit-grep sentinel this suite inherits.
- `docs/architecture/kca-cli-architecture.md` — the four-layer CLI
  shape `kca eval` slots into.
- `docs/evidence/m13/T000/discovery/` — Discovery / Debate Gate
  transcripts that shaped the six decisions in ADR-0019.
