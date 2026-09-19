# ADR-0019: Evaluation regression-suite framework

_Renumbered from ADR-0016 during M11+M12 merge integration on 2026-06-09: M11 took ADR-0016 (CTF data model) and ADR-0017 (CTF approval gates); M12 took ADR-0018 (generalized competition-type enum). M13's ADR moves to 0019. Content unchanged._

## Status

Proposed (M13, 2026-06-09). Subject to confirmation on the M13 proposal issue after the Discovery / Debate Gate transcripts at `docs/evidence/m13/T000/discovery/` have been reviewed.

## Context

M0–M10 shipped the platform's primary surfaces (worker, CLI, skills, audit trail, telemetry, decision API, notebook-submission path). M13's job is to make every subsequent platform change **measurable**: an arbitrary code change on `main` must be evaluable against a fixed, checked-in set of suites so future PRs can be graded against the prior baseline rather than against vibes.

M13 is the first internal regression milestone. It is NOT a leaderboard-chasing milestone and NOT an LLM-quality milestone — the score *values* it produces are baselined, not gated. Pass/fail in M13 is structural: did the suite run, did it record the expected metrics, did the report writer produce a diffable snapshot.

This ADR pins the regression-suite framework's schema, driver shape, route selector, cost gate, fixture posture, and replay determinism. T001 lands the migration and CLI scaffold; T002–T007 fill the individual suites; T008 wires the nightly cron; T009 closes the milestone. The architecture doc [`docs/architecture/eval-regression-suite.md`](../architecture/eval-regression-suite.md) carries the ASCII data-flow, table layouts, and per-suite metric contracts that this ADR's decisions imply.

Inputs that shape this ADR:

- ADR-0007 (OTEL strategy) and ADR-0013 (multi-exporter wiring) — the multi-consumer pattern (developer terminal, local SQLite, Supabase) is reused for eval reports.
- ADR-0010 (per-job-type model routing) — the existing `src/worker/routing.py` is the source of truth for `--route` values.
- ADR-0006 (configurable approval gates) — the new `external_llm` gate follows the same per-project/per-job override pattern.
- ADR-0008 (artifact storage local-first) — eval report Markdown lands under `runs/m13-eval/<timestamp>/report.md` to mirror the existing run-artifact layout.
- M10-T007 audit-grep sentinel — every M13 suite must inherit the "0 lines for `kaggle competitions submit` / `kaggle kernels push` / `kaggle datasets create`" guard. The eval harness MUST NOT add a new leak path.
- Discovery / Debate Gate (M9.4) — transcripts at `docs/evidence/m13/T000/discovery/` informed every decision below.

## Decision

The eval regression suite ships as a six-decision package:

### 1. Schema — three new tables (`eval_suites`, `eval_runs`, `eval_results`)

Three tables, not one wide table:

- `eval_suites` — slow-changing registry of suite metadata (`slug`, `display_name`, `category`, `default_route`, `requires_db`, `requires_remote`). One row per registered suite. Edited only via migration / `kca eval` registration.
- `eval_runs` — one row per `kca eval run` invocation. Carries the run-level context: `started_at`, `ended_at`, `git_sha`, `route_summary`, `kca_dry_run`, `budget_cap_usd`, `status` (`running` / `ok` / `aborted_on_budget` / `aborted_on_error`).
- `eval_results` — one row per (case × route) executed under a given `eval_run_id`. Carries per-case status, latency, cost, and a free-form `metrics_jsonb` column whose keys are defined per suite (see architecture doc §"Per-suite metric definitions").

Why three tables, not one:

- Each suite's `metrics_jsonb` keys are heterogeneous (a tool-smoke case emits `bytes_written` / `exit_code`; a Kaggle replay case emits `cv_score` / `rmsle` / `fit_seconds`). A single wide table forces every row to carry every column or accept sparse NULLs, which makes per-suite queries painful and per-suite indexes wasteful.
- Run-level metadata (git SHA, budget cap, dry-run flag) is the same for every case in a given run; storing it on each case-level row is duplication that goes stale on any future schema change.
- The grain split lets `kca eval report` aggregate by `eval_run_id` × `suite_id` × `route` without re-deriving the per-run context.
- The split mirrors the existing `experiments` → `experiment_runs` → `experiment_run_metrics` grain already proven in M2 / M9.

Indexes: `eval_results (eval_run_id, suite_id, route)`, `eval_runs (started_at desc)`, `eval_suites (slug unique)`. Foreign keys: `eval_results.eval_run_id → eval_runs.id`, `eval_results.suite_id → eval_suites.id`, `eval_runs.project_id → projects.id` (nullable; nightly cron rows attach a synthetic platform project).

### 2. Driver shape — per-suite Python module

Each suite is a Python package under `tools/kca/eval/suites/<slug>/` exposing two contracts:

```python
def register() -> SuiteSpec:
    """Return suite metadata for `eval_suites` ingestion."""

def run(case: CaseSpec, route: RouteSpec) -> EvalResult:
    """Execute one case under one route. Pure-ish: no
    network outside the route layer; no Kaggle CLI; no
    cross-case shared mutable state."""
```

Why this shape:

- It mirrors the M7 tool registry's `(name, side_effect, approval_label)` pattern: declarative metadata is registered once; runtime behaviour is a stable function signature the harness composes.
- A per-suite module is grep-able. `tools/kca/eval/suites/tool_smoke/` is the only place to look when "what's in the tool-smoke suite" is the question. A monolithic suite registry would scatter that information across many functions.
- The `(case, route) -> EvalResult` contract makes the route-comparison harness (T006) trivial: call `run(case, route)` for the cartesian product the user requested.
- The contract forbids cross-case shared state, which is what makes replay-deterministic seeding (decision 6 below) actually hold.

Each suite ships with its own fixtures under `tests/fixtures/<slug>/` (checked-in, ≤ ~5 MB per fixture).

### 3. Route selector — reuse `src/worker/routing.py` + add `mocked`

`--route` accepts:

- Any key already in `MODEL_ROUTES` from `src/worker/routing.py` — the routing table from ADR-0010 is the source of truth. Today this means `research` / `implement` / `experiment` / `eval` / `analysis` / `review` / `log_triage` / `summarise`, which resolve to the configured Anthropic / local-vllm model.
- Direct model ids the routing layer accepts as `override` — `claude-sonnet-4-6`, `claude-haiku-4-5`, `claude-opus-4-7`, `gpt-4o`, the local-vllm probe sentinel, etc.
- A new `mocked` route that short-circuits to `litellm.mock_completion` with the per-suite fixture string. Default for any `kca eval run` invocation that does not set `KCA_ALLOW_REMOTE=1`.

Why this shape, not a new routing layer:

- ADR-0010 already pinned the routing decision. The eval harness is a caller, not a peer; introducing a parallel route table would create the exact drift the legacy `kkr.py` migration suffered from (see `docs/meeting-notes/2026-05-24-r3.md` §6 and ADR-0010).
- `mocked` is the only route the harness OWNS. Every other route is a thin pass-through to `src/worker/routing.py`'s `model_for(...)`.
- The `mocked` route's fixture string lives next to the case fixtures in `tests/fixtures/<slug>/`, so a "what would the LLM say" change is a regular code-review diff, not a magic constant.

### 4. Cost gate — per route invocation, harness-enforced

The `external_llm` approval gate fires **per route invocation**, not per case. A single `kca eval run --suite reasoning --route claude_opus_4_7` that has 10 cases counts as one gate fire with one `human_decisions` row and one budget commit; the harness then enforces the budget cap across all 10 cases.

Why per-invocation, not per-case:

- Per-case would generate N `human_decisions` rows per run, swamping the decision queue and creating a "click to continue" interaction pattern that is exactly what ADR-0006 was meant to avoid for routine workflows.
- The budget cap is the actual control — once a per-run cap is approved, finer-grained gates add no safety. A run that exceeds the cap mid-execution aborts with `status = aborted_on_budget` on the `eval_runs` row, and the remaining cases are not started.
- The harness enforces the cap, NOT `litellm`. `litellm`'s per-completion-call cost is treated as a measurement; the running total is computed in the harness and compared to the cap before the next case dispatches.
- Routes `mocked` and `local_vllm` do NOT trigger `external_llm` and carry no cost.

Per ADR-0006 the gate is configurable per project / per job; the default for the nightly cron is `--route mocked`, which means the gate never fires in unattended scheduling.

### 5. Fixture posture — frozen, checked-in, offline-only

Every Kaggle replay reads a **frozen sub-sample** under `tests/fixtures/<comp>/`. The fixture is checked in. The fixture is ≤ ~5 MB per competition. The fixture is NEVER refreshed from real Kaggle inside a suite; refreshes are a separate, human-initiated maintenance step.

Why frozen-and-checked-in:

- The whole point of regression is determinism. A fixture that re-fetches from Kaggle changes the suite's input on a schedule external contributors do not control.
- The audit-grep sentinel from M10-T007 (0 lines reach the kaggle CLI from any suite process) is only meaningful if there is no legitimate code path that calls `kaggle competitions download` inside a suite. The fixture posture is what makes the sentinel cheap to enforce.
- 5 MB × ~10 fixtures = ~50 MB worst case in the repo. That is acceptable for the value of reproducibility; if a single fixture exceeds 5 MB, sub-sample it further or move it to a release artefact and document the path.

### 6. Replay determinism — fixed seeds + mocked completions

Every suite, on entry to `run(case, route)`:

- Calls `random.seed(0)` and `numpy.random.seed(0)` (only the modules the case actually uses; not a blanket monkey-patch).
- If `route == "mocked"`, pins the LLM-emitted text via `litellm.mock_completion(model=..., custom_response=<fixture>)`.
- Records the seed-and-route triple in `eval_results.context_jsonb` so a future "why did this row differ" investigation has the reproducer in-band.

Why fixed `0`, not a per-case seed:

- A per-case seed is just one more thing to remember to change. With a single fixed seed, the only sources of variance are (a) the input case fixture, (b) the route's output, and (c) the suite code itself — all of which are intentionally version-controlled.
- For the route-comparison harness (T006), holding the seed constant across routes is exactly the desired comparison: "given identical inputs and identical RNG state, how does route A vs B score?".

Suites that NEED a non-zero seed (e.g. to stress-test a stochastic estimator's stability) can declare a per-case `seed_override` in their `CaseSpec`, recorded in `eval_results.context_jsonb`.

## Addendum (M14-T009, issue #63): per-suite `failure_threshold` + PR gate

M13 shipped the suites and the nightly *informational* diff. M14-T009 adds a **blocking** PR gate (`eval-delta-check`) that compares a PR's mocked run against the checked-in baseline snapshot (`eval/baselines/mocked-baseline.json`) and fails the PR if any suite regresses past its threshold. Two threshold kinds:

- **Absolute (shape-check suites).** `tool_smoke`, `kernel_dryrun`, `reasoning`, and the deterministic shape of `kaggle_replay_*` are pass/skip-deterministic under `--route mocked`. Their threshold is absolute and strict:
  - `fail` count MUST stay `0` (any new failing case regresses).
  - `error` count MUST stay `0`.
  - `audit_grep_violations` MUST stay `0` (M10-T007 sentinel inheritance).
  - `pass` count MUST NOT drop below baseline (a case flipping pass→skip is a regression unless the baseline is re-pinned).

  | Suite | baseline pass | floor (`pass >=`) | `fail` | `error` | `audit_grep` |
  |---|---:|---:|---:|---:|---:|
  | `tool-smoke` | 10 | 10 | 0 | 0 | 0 |
  | `reasoning` | 5 | 5 | 0 | 0 | 0 |
  | `kernel-dryrun` | 2 | 2 | 0 | 0 | 0 |
  | `kaggle-replay-titanic` | 1 | 1 | 0 | 0 | 0 |
  | `kaggle-replay-spaceship-titanic` | 1 | 1 | 0 | 0 | 0 |
  | `kaggle-replay-house-prices` | 1 | 1 | 0 | 0 | 0 |

- **Relative (metric deltas).** When a `kaggle_replay_*` suite emits a `cv_score` (live/non-mocked route), the gate allows a small relative drift before flagging a regression. Direction is metric-aware:
  - higher-is-better (`accuracy`, `auc`): fail if `cv_score < baseline_cv_score * (1 - REL_TOL)`.
  - lower-is-better (`rmsle`): fail if `cv_score > baseline_cv_score * (1 + REL_TOL)`.
  - `REL_TOL = 0.02` (2%) default, per-suite overridable in the baseline snapshot's `metric_thresholds` block. Under `--route mocked` (the PR gate's default) no `cv_score` is emitted, so only the absolute shape thresholds apply; the relative rule arms only when a baseline carries a recorded `cv_score`.

**Bypass — `eval:waive-delta` (human-only).** A repository maintainer may add the `eval:waive-delta` label to a PR to skip the blocking gate (e.g. an intentional baseline change). The waiver is **not silent**: the gate requires a rationale comment on the PR and records the waiver in `agent_tool_audit` (tool `eval_delta_check`, decision `waived`, with the PR number, the actor, and the rationale) so the bypass is auditable. A waived run still computes and prints the delta for the record; it just does not fail the check.

The gate **reuses the M13 nightly runner**: the same `kca eval run --all --route mocked --dry-run --json` invocation and the same clean-env / audit-grep guarantees; only the trigger (PR vs cron) and the comparison target (checked-in baseline vs previous nightly artefact) differ.

## Consequences

- **Positive.** The platform gains a measurable baseline. Any future PR can run `kca eval run --all --route mocked` and produce a before/after diff. The CI nightly cron (T008) makes this automatic.
- **Positive (M14-T009).** The `eval-delta-check` PR gate turns the baseline from informational into blocking: a PR that regresses a suite past its threshold cannot merge without an audited `eval:waive-delta` waiver.
- **Positive.** Per-suite Python modules make it easy to grep "what exactly is the tool-smoke suite checking" and to add a new suite in one place.
- **Positive.** Reusing `src/worker/routing.py` prevents the eval harness from drifting away from the worker's routing decisions.
- **Negative.** Three new tables means migration 0010 and three new helper modules in `tools/kca/db.py`. The schema is small (one new registry table, one new run table, one new results table — same pattern as `experiment_runs` / `experiment_run_metrics`), so the ongoing maintenance is comparable to one existing migration.
- **Negative.** Frozen fixtures will drift from Kaggle reality. The Titanic dataset is stable enough that this is acceptable; less stable competitions (e.g. live competitions) are explicitly out of scope for M13. M13.1 / M13.2 will revisit if needed.
- **Negative.** A per-invocation `external_llm` gate means a misconfigured cap CAN burn the full budget in one mid-run dispatch before the next budget check. Mitigated by (a) requiring the cap to be set on the M13 proposal issue before T006 may run any non-mocked route and (b) recording `aborted_on_budget` cleanly on the `eval_runs` row.
- **Deferred.** CTF / hackathon eval cases (M11 / M12) and live Kaggle replay are out of scope. M13.1 / M13.2 / M14 own them.

## Cross-references

- [`docs/architecture/eval-regression-suite.md`](../architecture/eval-regression-suite.md) — ASCII data-flow, per-table column lists, per-suite metric definitions, route secrets map, audit-grep sentinel inheritance.
- [`docs/evidence/m13/T000/discovery/requirements-skeptic.md`](../evidence/m13/T000/discovery/requirements-skeptic.md)
- [`docs/evidence/m13/T000/discovery/design-red-team.md`](../evidence/m13/T000/discovery/design-red-team.md)
- [`docs/evidence/m13/T000/discovery/SKIP-NOTE.md`](../evidence/m13/T000/discovery/SKIP-NOTE.md) (legacy-archaeologist skip — greenfield)
- ADR-0006 (approval gates) — `external_llm` is a new gate name; same policy plumbing.
- ADR-0010 (per-job-type model routing) — `--route` reuses `MODEL_ROUTES`.
- ADR-0013 (OTEL exporters) — eval reports may borrow the three-consumer (console / SQLite / Supabase) export pattern in a future revision; this ADR does not commit to it.
- `docs/architecture/discovery-debate-gate.md` — the gate this task exercises.
- `docs/tasks/m13/M13-T000-eval-architecture.md` — the spec this ADR fulfills.
