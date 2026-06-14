# design-red-team report for M13-T000 (eval regression-suite framework)

Source: strawman `docs/adr/0019-eval-regression-suite.md`,
companion `docs/architecture/eval-regression-suite.md`,
spec `docs/tasks/m13/M13-T000-eval-architecture.md`.

Upstream:
- legacy-archaeologist: SKIPPED — `docs/evidence/m13/T000/discovery/SKIP-NOTE.md` (greenfield).
- requirements-skeptic: `docs/evidence/m13/T000/discovery/requirements-skeptic.md`.

_Produced under the M9.4 Discovery / Debate Gate. The agent body
lives in `.claude/agents/design-red-team.md`; this artefact is a
manual execution of that agent's protocol, following the precedent
set by `docs/evidence/m9_4-kkr-replay/design-red-team.md`. The
"proposed design" being refuted is the ADR-0019 strawman + the
companion architecture doc at HEAD of branch `worktree-m13-execution`._

Acceptance line (verbatim):

> Output MUST include ≥3 alternatives, ≥1 dropped capability with
> file:line evidence, all four long-term-cost axes, and ≥1
> actionable `open_disagreements` entry.

## alternatives

1. **Single wide table (`eval_results` only).** Collapse the three
   proposed tables into one. Each row carries run metadata
   (`git_sha`, `route_summary`, `budget_cap_usd`), suite metadata
   (`suite_slug`, `category`, `default_route`), and per-case data
   (`case_slug`, `route`, `status`, `cost_usd`, `metrics_jsonb`).
   Sketch: one migration adds one table; the `kca eval report`
   aggregator reads with a single `WHERE eval_run_id = …` filter;
   suite registration becomes an INSERT … ON CONFLICT against a
   subset of columns instead of a separate `eval_suites` table.
   Key tradeoff vs proposal: zero JOINs in the report path, simpler
   migration, but every row duplicates `git_sha` / `budget_cap_usd`
   / `route_summary`. For the cron's expected volume (~10 cases ×
   ~5 routes × 365 nights = ~18,250 rows/year), the duplication
   cost is real but small. The proposal's three-table split mirrors
   `experiments` / `experiment_runs` / `experiment_run_metrics`
   (see `docs/adr/0010-model-routing.md` references and existing
   migration `supabase/migrations/0006_m6_reviews_spans.sql:12-58`),
   which is a known-good shape — but is overkill for a regression
   suite that has no human-edited "experiment" surface above it.

2. **`eval_results` as a `agent_telemetry_spans` extension.** Treat
   every per-case result as an OTEL span with attributes carrying
   the metric keys, and reuse `src/worker/telemetry.py`'s exporter
   stack (console / SQLite / Supabase) from ADR-0013. Sketch: the
   harness wraps `run(case, route)` in
   `with tracer.span(kind="eval_case", ...)`, attaches metrics as
   span attributes, lets the ADR-0013 SQLite / Supabase exporters
   write them, and re-uses the `v_agent_telemetry_spans_recent`
   view (or its M13 equivalent) for the report aggregator. Key
   tradeoff vs proposal: zero new tables, automatic three-consumer
   export (developer terminal / local SQLite / Supabase), and the
   `agent_telemetry_spans` row is already the right grain. But span
   schemas are deliberately string-typed and free-form (see the
   `agent_telemetry_spans` insert path); enforcing the per-suite
   metric contracts the architecture doc §"Per-suite metric
   definitions" promises becomes harness-side rather than
   schema-side, and a stray attribute key never raises an error.

3. **Pytest-as-harness.** Treat each suite as a pytest module under
   `tests/eval/<slug>/`, use existing pytest fixtures for the
   per-case parametrisation, write per-case results into a SQLite
   under `runs/m13-eval/<ts>/results.sqlite` via a pytest plugin
   (no Supabase write at all for the regression baseline), and let
   the report aggregator be a thin SQLite query. Sketch: the
   nightly cron is `pytest tests/eval -q --eval-output
   runs/m13-eval/$(date +%s)/`; the report writer reads the
   sqlite, emits report.md / report.json, and `gh issue comment`s
   the diff. Key tradeoff vs proposal: zero new tables in Supabase,
   one fewer migration, native CI integration (every nightly cron
   is already running pytest in `.github/workflows/test.yml`). But
   the regression results then live in an artefact, not in the
   platform's data plane; a future UI that wants to show "M13 eval
   over time" must re-ingest the artefacts. Closest evidence for
   the pytest-fixture pattern: `tests/test_m9_e2e.py`,
   `tests/test_m10_e2e.py` already do near-this for offline replay.

4. **Per-suite, per-route subprocess isolation.** Keep the three-
   table schema, but execute each suite × route combination in a
   fresh `python -m tools.kca.eval._run_one_case --suite <s>
   --case <c> --route <r>` subprocess. The harness shells out
   instead of calling `run(case, route)` in-process. Sketch: each
   subprocess loads only the env vars relevant to its route
   (preventing the `requirements-skeptic` §personas_and_accounts #3
   cross-route credential bleed), seeds RNG in its own interpreter,
   and writes back to Supabase as its last act. Key tradeoff vs
   proposal: ~10–100 ms subprocess startup × ~50 case-route
   combinations per cron run ≈ 5 seconds of overhead per nightly,
   which is acceptable; in exchange the env-isolation guarantee is
   structural rather than a code-discipline guarantee. Closest
   precedent: `tools/legacy/kkr.py:528–548` per-owner subprocess
   isolation lifted from the kkr migration archaeology.

## dropped_capabilities

- **OTEL three-consumer export of eval rows.** ADR-0013 ships a
  multi-exporter stack (`docs/adr/0013-otel-console-sqlite-supabase.md:23-50`)
  that emits every worker / tool / LLM span to console / SQLite /
  Supabase. The proposed `eval_results` table is a *fourth* sink
  outside that pipeline; the developer running `kca eval run` on
  their laptop does not get the "console stderr line per finished
  span" UX that ADR-0013's console exporter promises for every
  other observable thing on the platform. Survives in:
  alternative 2 (telemetry-spans extension), legacy (the worker's
  own per-LLM-call spans already flow there). Evidence:
  `docs/adr/0013-otel-console-sqlite-supabase.md:42-48` (the
  Supabase exporter's `db.record_span(...)` best-effort hook is
  exactly the shape `eval_results` could re-use).

- **Per-route credential isolation.** The proposed harness is
  implicitly single-process; the architecture doc §"Route secrets
  map" reads secrets via `src/worker/routing.py`, but a single
  Python process inherits `os.environ` exactly as it was at `kca
  eval run` time. The kkr archaeology established that
  `_load_env_for_owner` mutates `os.environ` and leaks credential
  state across jobs (`tools/legacy/kkr.py:541-548`,
  `tools/legacy/kkr.py:587-595`, refuted in
  `docs/evidence/m9_4-kkr-replay/design-red-team.md` alternative 2).
  M13's proposal does NOT inherit the per-job env-isolation
  improvement those alternatives recommended. Survives in:
  alternative 4 (subprocess isolation), legacy kkr's per-owner
  subprocess sketch.

- **Pytest-collection of regression cases.** Today `tests/` already
  contains regression-shaped offline replays
  (`tests/test_m9_e2e.py:1-50`, `tests/test_m10_e2e.py`; the M13
  loop-prompts doc explicitly calls them the "closest offline
  replay precedents"). The proposed three-table framework writes
  case results to Supabase but does NOT expose those cases to the
  pytest collector — so a `pytest -k "eval"` invocation does not
  enumerate them, and CI cannot fail a PR on a regression unless
  it goes through the new `kca eval run` verb. Survives in:
  alternative 3 (pytest-as-harness), legacy (M9 / M10 e2e tests
  are still pytest-collectible). Evidence:
  `tests/test_m10_e2e.py` file existence and the M13 loop-prompts
  doc citation under "Required tests / evidence".

- **Per-case `human_decisions` row.** ADR-0006 (`docs/adr/0006-configurable-approval-gates.md:111-118`)
  pairs every approval-gated operation with a `human_decisions`
  row. ADR-0019 §"Cost gate" explicitly chooses per-invocation
  gating to avoid N×decision-row spam, which means the per-case
  audit trail of "which case ran under approval id X" is lost — a
  query "for which case was the budget exceeded" requires
  re-deriving from `eval_results.cost_usd` accumulation. Survives
  in: a future variant of the proposal that records
  `eval_runs.approval_id → human_decisions.id` (currently absent
  from the schema). Evidence: `docs/adr/0006-configurable-approval-gates.md:114`
  (the `Inserts a human_decisions row with status='pending'`
  contract).

- **Real-time progress visibility for the M13 nightly cron.** The
  proposed `eval_runs.status` flips from `running` to a terminal
  status at the end of the run, with no intermediate progress
  field. The M10 telemetry SQLite exporter
  (`docs/adr/0013-otel-console-sqlite-supabase.md:30-37`) was
  designed precisely so a long-running job could be inspected
  mid-flight from `.agent/telemetry.sqlite`. The proposal forfeits
  that for eval rows. Survives in: alternative 2 (telemetry-spans
  extension), legacy (existing OTEL stack).

## long_term_costs

cognitive_load:    A new contributor must learn (a) three new tables,
                   (b) the `register()` / `run(case, route) -> EvalResult`
                   contract, (c) the per-suite `metrics_jsonb` schema,
                   (d) the audit-grep sentinel inheritance, AND
                   (e) the relationship between the existing
                   `runs/<comp>/<run_id>/` artefact layout and the
                   sibling `runs/m13-eval/<ts>/`. The OTEL-extension
                   alternative collapses (a) to "it's just a span"
                   and (e) to "it's the existing telemetry stack",
                   but trades that for "every metric is a stringly-
                   typed attribute on a span". The pytest-as-harness
                   alternative collapses (a)–(e) to "it's a pytest
                   module" but loses the platform's data-plane view
                   of eval history.

ops_burden:        At 3am the failure modes are: (i) the nightly
                   cron's `gh issue comment` exceeds GitHub's 65k
                   char cap and silently drops the rolling diff;
                   (ii) `eval_runs.status = running` rows accumulate
                   because the harness crashed mid-run with no
                   heartbeat sweeper; (iii) a flaky
                   `tests/fixtures/<slug>/*.csv` line-ending change
                   on Windows / WSL contributors makes the SHA
                   assertions in the report aggregator spuriously
                   regress. Each of these is solvable, but none is
                   addressed by the strawman.

extensibility:     Two named near-term scope expansions: (A) M13.1
                   CTF eval cases and (B) M13.2 Devpost / hackathon
                   eval cases (per M13 §"What's NOT in scope"). The
                   three-table schema scales to both — they are
                   additional rows in `eval_suites`. But each will
                   bring metric keys (CTF: `flags_captured`,
                   `solver_seconds`; Devpost: `submission_count`,
                   `judge_rubric_score`) that the T007 aggregator
                   must learn. Without an explicit metric-schema
                   versioning convention (see requirements-skeptic
                   §hidden_constraints #2), the M13.1 PR is also a
                   T007 refactor PR.

blast_radius:      If the eval framework breaks: (i) the CI nightly
                   cron is red but `main` is shippable — low impact;
                   (ii) a flaky audit-grep sentinel false-positives
                   on a benign log line and aborts every nightly —
                   medium impact (PRs cannot regression-check
                   against a green baseline until someone fixes the
                   pattern); (iii) the `external_llm` gate
                   misfires under T006 and an approved $0.50/run
                   becomes a $50 run because the harness's
                   running-total calculation drifts off LiteLLM's
                   actual billing — high impact (real money) and
                   the only mitigation is the per-run hard cap. A
                   credential leak into a checked-in fixture
                   string is the worst case — same posture as the
                   M9 dotenv leak (issue #11) but on the LLM side.

## open_disagreements

- **Per-case `human_decisions` row vs per-invocation gating.** The
  proposal optimises for "one click per run" UX; the dropped
  capability above argues this trades away per-case auditability.
  Next step: ask the human (on the M13 proposal issue) whether
  per-invocation gating is acceptable for T006, and if so,
  document the trade explicitly in ADR-0019's "Consequences" so
  later auditors do not relitigate it.

- **OTEL-spans-as-storage vs new tables.** Alternative 2 is the
  closest competing design and has the lowest schema-cost. The
  proposal's argument for new tables (per-suite metric keys are
  heterogeneous; ADR-0019 §1) is real, but the OTEL exporter
  already accepts arbitrary attribute dicts. Next step: write a
  spike — implement one suite (T002 tool-smoke) BOTH ways and
  compare the report aggregator's SQL surface, then update
  ADR-0019 with the chosen path. If the spike shows OTEL-as-storage
  is feasible, the milestone can deprecate `eval_results` entirely
  before T002 commits to its schema. Defer-to-follow-up-issue
  labels: `type:research`, `area:eval`, `area:supabase`,
  `decision:needed`.

- **Pytest collection of eval cases.** Alternative 3 is the
  cheapest in lines-of-code, but loses the platform-data-plane
  view of eval history. Next step: defer to a follow-up issue
  labelled `type:feature`, `area:eval`, `area:testing` — a thin
  pytest plugin that materialises each `eval_results` row as a
  pytest test result, so `pytest -k "eval"` still works AND the
  Supabase rows still land. This is a pure additive change after
  T002 commits to its schema; not blocking for T000.

- **Subprocess isolation for paid routes.** Alternative 4 is the
  most expensive in startup time (~5 seconds per cron) but
  eliminates the kkr-style ambient-credential failure mode the
  legacy archaeology surfaced. Next step: ask the human on the
  M13 proposal issue whether ambient `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
  in a single-process harness is acceptable for T006, OR whether
  the subprocess split is a hard requirement before any paid
  route may run. Without an answer, T006 lands as ambient-env by
  default and the failure mode is re-discovered the first time a
  contributor's shell has a stale key.

- **Audit-log retention and commit posture.** The architecture
  doc says `report.md` is committed; it does NOT say
  `runs/m13-eval/<ts>/audit/*.log` is committed. The
  requirements-skeptic §side_effects #2 flag is real: an
  accidental `git add runs/m13-eval/<ts>/` could leak credential-
  shaped substrings. Next step: file a follow-up issue
  (`area:eval`, `area:ci`, `policy:approval-required`) to add an
  explicit `.gitignore` entry plus a CI pre-commit check that
  refuses to stage any path under `runs/m13-eval/*/audit/`.
  Implement before T002 lands a real audit-log directory.

- **`git_sha` recorded on `eval_runs`: worktree HEAD vs `main`.**
  The proposal records worktree HEAD; this is reproducible but
  not comparable across runs from different worktrees. Next step:
  decide in ADR-0019's next revision (after the gate verdict)
  whether to record both — `eval_runs.git_sha_worktree` and
  `eval_runs.git_sha_main_base` — or to commit to one. Defer
  decision to T001 owner; do not block T000.
