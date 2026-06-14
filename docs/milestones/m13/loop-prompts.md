# M13 — Loop Prompts

_Evaluation, reliability, and regression suite — measures whether the
platform improves over time._
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M10 exit confirmed (notebook-submission path validated;
see `docs/milestones/m10/final-review.md`). M11 (CTF) and M12 (Devpost) are NOT
prerequisites — their eval cases are deferred to follow-ups._
_Shared rules: every Loop Prompt below MUST follow
`docs/milestone-loop-protocol.md` (sequencing, no real Kaggle /
Anthropic outside designated paths, DB DSN + sandbox bypass,
per-milestone worktree by default, secret denylist, Discovery / Debate
Gate on `arch:` tasks)._

---

## M13 at a glance

M13 is the first **internal regression milestone** — it does not chase
a leaderboard or ship a user-visible feature. Its job is to make every
later platform change measurable. After M13, an arbitrary code change
on `main` can be evaluated against a fixed set of suites (tool-smoke,
Kaggle replay, notebook/kernel dry-run, reasoning, model-route
comparison) and produce a metrics snapshot that future PRs can be
graded against.

This is also the first milestone whose entry task (`M13-T000`) is
tagged `arch:` and therefore triggers the **Discovery / Debate Gate**
(M9.4): `legacy-archaeologist` (skippable — greenfield), then
`requirements-skeptic`, then `design-red-team`. ADR-0019 must cite all
three transcripts under `docs/evidence/m13/T000/discovery/` before any
implementation begins.

M13 is **not** a leaderboard-chasing milestone and **not** an
LLM-quality milestone. Pass/fail is structural: did the suite run,
did it record the expected metrics, did the report writer produce a
diffable snapshot. The metric *values* are baselined here, not
gated.

Direct entry into M13 is blocked until **all** are true:

- M10 is merged on `main` (`docs/milestones/m10/final-review.md` exists and
  reports PASS). The notebook/kernel fixtures from M10-T007 are the
  seed for `M13-T004`.
- M9 dry-run leak (issue #11) remains CLOSED on `main` — the eval
  harness inherits the same secrets posture; if #11 reopens, halt T008.
- Local Supabase container is running; M0–M10 migrations are applied;
  the existing `competitions` / `experiment_runs` / `submissions` /
  `agent_reviews` / `agent_tool_audit` rows from M9 / M10 are
  reachable. M13's new tables sit alongside them.

### What's in scope

| Capability | Owned by | M13 touches |
|---|---|---|
| Regression-suite framework + metrics schema | `docs/adr/0019-eval-regression-suite.md` + `docs/architecture/eval-regression-suite.md` | T000 |
| `eval_suites` / `eval_runs` / `eval_results` tables | `supabase/migrations/0010_m13_eval.sql` + `tools/kca/db.py` | T001 |
| `kca eval` CLI surface (`list`, `run`, `show`, `report`) | `tools/kca/eval.py` + `tools/kca/kca.py` registration | T001 — scaffold; T002–T007 — fill |
| Tool-smoke suite (deterministic, no LLM) | `tools/kca/eval/suites/tool_smoke/` + fixtures | T002 |
| Kaggle classic-practice replay (Titanic / Spaceship Titanic / House Prices) | `tools/kca/eval/suites/kaggle_replay/` + fixtures | T003 |
| Notebook/kernel dry-run regression | `tools/kca/eval/suites/kernel_dryrun/` (reuses M10 fixtures) | T004 |
| Reasoning-heavy benchmark | `tools/kca/eval/suites/reasoning/` + 5–10 fixed prompts + deterministic + rubric judges | T005 |
| Model-route comparison harness | `src/worker/routing.py` reuse + `tools/kca/eval/router.py` + cost budget | T006 |
| Metrics aggregator + Markdown / JSON report | `tools/kca/eval/report.py` + `kca eval report` | T007 |
| CI nightly cron + smoke / e2e tests | `.github/workflows/eval.yml` + `tests/test_m13_smoke.py` + `tests/test_m13_e2e.py` | T008 |
| Final review | `milestone-final-review` skill + `worktree-milestone-pr` skill | T009 |

### What's NOT in scope

- **CTF/lab eval cases.** Deferred to M13.1 (or whatever sub-milestone
  M11 produces). M11 has not landed; its solver-script / writeup
  artefacts are not yet stable enough to baseline against.
- **Hackathon / Devpost eval cases.** Deferred to M13.2 — see M12.
- **Real Kaggle network calls.** None. The whole point of replay is
  that the suites run offline against checked-in fixtures. T006's
  model-route comparison may call real LLM APIs under explicit budget
  cap and `--route` flag; Kaggle remains offline in every suite.
- **Production Supabase.** Local only.
- **New leaderboard chases.** M13 does not push a new Kaggle
  submission, kernel, dataset, or model. M9-T004 and M10-T004 are the
  only "real Kaggle write" rows in the system; M13 reads them but
  does not extend them.
- **Pass/fail thresholds on LLM quality.** M13 baselines values; future
  milestones (M14+) decide whether to gate PRs on score-deltas.
- **New top-level CLI subcommands beyond `kca eval`.** Internal
  helpers and per-suite drivers may live under `tools/kca/eval/`, but
  the CLI surface stays at one new top-level subcommand.

DB / sandbox details: see `docs/milestone-loop-protocol.md` §3 — the
local `supabase-db` container (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`)
needs `dangerouslyDisableSandbox=true`. T006's optional live-LLM
route also needs sandbox bypass; default is the local-vllm route or
`--dry-run` (mocked LLM via `litellm.mock_completion`).

---

## M13 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M13-T000 | `arch:` Regression-suite design + ADR-0019 + Discovery / Debate Gate transcripts | Prompt 0 |
| M13-T001 | Migration 0010 (`eval_suites` / `eval_runs` / `eval_results`) + `kca eval` CLI scaffold | Prompt 1 |
| M13-T002 | Tool-smoke suite (deterministic; no LLM; per-tool fixture inputs/outputs; ≥10 cases) | Prompt 2 |
| M13-T003 | Kaggle classic-practice replay suite (Titanic / Spaceship Titanic / House Prices fixtures; offline) | Prompt 3 |
| M13-T004 | Notebook/kernel dry-run regression — reuses M10-T007 fixtures + reviewer-gate stub | Prompt 4 |
| M13-T005 | Reasoning-heavy benchmark — 5–10 fixed prompts; deterministic + rubric judges | Prompt 5 |
| M13-T006 | Model-route comparison harness — Claude / GPT / local vLLM; cost cap; `--route` selector | Prompt 6 |
| M13-T007 | Metrics aggregator + `kca eval report` (JSON + Markdown snapshot) | Prompt 7 |
| M13-T008 | CI nightly cron + `tests/test_m13_smoke.py` + `tests/test_m13_e2e.py` | Prompt 8 |
| M13-T009 | M13 exit criteria validation + `docs/milestones/m13/final-review.md` | Prompt 9 |

Each task's full scope, acceptance criteria, allowed / forbidden paths,
and closeout format live in the matching `docs/tasks/m13/M13-T00N-*.md`
spec.

---

## Loop Prompt 0 — M13-T000 Regression-suite design + ADR-0019 (arch:)

```
/goal Execute M13-T000 regression-suite architecture + ADR-0019 + Discovery / Debate Gate transcripts until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md (note §7 — Discovery / Debate Gate is MANDATORY for this `arch:` task)
Task spec: docs/tasks/m13/M13-T000-eval-architecture.md

Read also (background context):
- docs/milestones/README.md §M13
- docs/architecture/discovery-debate-gate.md
- .claude/agents/requirements-skeptic.md
- .claude/agents/legacy-archaeologist.md (skippable — greenfield; document the skip)
- .claude/agents/design-red-team.md
- docs/adr/0010-model-routing.md (route routing precedent)
- docs/adr/0013-otel-console-sqlite-supabase.md (multi-exporter precedent)
- docs/architecture/kca-cli-architecture.md (existing CLI shape)
- src/worker/routing.py (per-job-type routing this milestone will reuse)
- tools/kca/run.py (existing run-artifact layout)

Mission (full version in task spec):
Write `docs/adr/0019-eval-regression-suite.md` and the companion
`docs/architecture/eval-regression-suite.md`. Run the Discovery /
Debate Gate (skip `legacy-archaeologist` only with an explicit
greenfield note). Attach all three transcripts under
`docs/evidence/m13/T000/discovery/`. No code, no migration, no CLI
changes in this Loop Prompt — design only.
```

---

## Loop Prompt 1 — M13-T001 Migration 0010 + `kca eval` CLI scaffold

```
/goal Execute M13-T001 migration 0010 (eval_suites / eval_runs / eval_results) + `kca eval` CLI scaffold until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T001-migration-and-cli.md

Read also (background context):
- M13-T000 closeout (ADR-0019 + architecture doc)
- supabase/migrations/0007_m8_agent_tool_audit.sql (most recent migration)
- supabase/migrations/0006_m6_reviews_spans.sql (the M6 pattern for new tables)
- tools/kca/db.py (helper functions for new tables follow the M6 / M8 pattern)
- tools/kca/kca.py (CLI registration)
- tools/kca/run.py (LOCAL_WRITE pattern)
- docs/architecture/kca-cli-architecture.md

Mission (full version in task spec):
Add `supabase/migrations/0010_m13_eval.sql` (the three tables and
their indexes), the matching helpers in `tools/kca/db.py`, and the
`kca eval` subcommand surface with four placeholder verbs
(`list`, `run`, `show`, `report`). No suites yet; the scaffold must
exit-0 with `--help` on each verb and refuse `run` with
"NO_SUITES_REGISTERED" until T002+ land.
```

---

## Loop Prompt 2 — M13-T002 Tool-smoke suite (deterministic; no LLM)

```
/goal Execute M13-T002 tool-smoke regression suite (≥10 cases; deterministic; no LLM) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T002-tool-smoke-suite.md

Read also (background context):
- M13-T000, M13-T001 closeouts
- src/worker/tools.py (the tool registry M13 evaluates)
- .kca/tools/tools.yaml (tool metadata)
- tests/test_m7_smoke.py (the M7 smoke test that already exercises some tools)
- tools/kca/eval/ (scaffold from T001)

Mission (full version in task spec):
Author ≥10 deterministic tool-smoke cases — per-tool fixed inputs and
expected outputs, no LLM, no Kaggle network, no Supabase write
outside the `eval_runs` / `eval_results` rows the suite itself
produces. Coverage target: every tool with `category=read_only` in
`tools.yaml`, plus the four most-used `local_write` tools.
```

---

## Loop Prompt 3 — M13-T003 Kaggle classic-practice replay (offline fixtures)

```
/goal Execute M13-T003 Kaggle classic-practice replay suite (Titanic / Spaceship Titanic / House Prices fixtures; offline) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T003-kaggle-replay-suite.md

Read also (background context):
- M13-T001, M13-T002 closeouts
- docs/tasks/m4/M4-T008-tc1-titanic-end-to-end.md (Titanic precedent)
- docs/tasks/m5/M5-T008-tc2-house-prices.md (House Prices precedent)
- docs/tasks/m9/M9-T002-baseline-loop.md (Spaceship Titanic LR precedent)
- docs/tasks/m9/M9-T005-second-experiment.md (HGB+FE precedent)
- tests/test_m9_e2e.py (dry-run pattern)
- tests/fixtures/spaceship-titanic/ (or equivalent — produce if missing)

Mission (full version in task spec):
Add three offline Kaggle replays: Titanic, Spaceship Titanic, House
Prices. Each replay reads a frozen sub-sample of the training CSV
(tens of rows), executes the M9-style baseline (or M5 House-Prices
equivalent), records local CV / RMSLE into `eval_results`. No real
Kaggle network. No real Anthropic call by default. The optional
`--route` flag is wired but defaults to `mocked`.
```

---

## Loop Prompt 4 — M13-T004 Notebook/kernel dry-run regression

```
/goal Execute M13-T004 notebook/kernel dry-run regression suite (reuses M10-T007 fixtures + reviewer-gate stub) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T004-notebook-kernel-dryrun-suite.md

Read also (background context):
- M13-T001, M13-T002 closeouts
- M10-T002, M10-T004, M10-T007 closeouts
- tests/test_m10_e2e.py (closest pattern; reuse the kg-nb round-trip
  + credentials-gate refusal cases)
- tools/kca/kg.py::cmd_push (the gate this suite asserts on)
- src/worker/reviewer.py (the reviewer-gate stub)
- tests/fixtures/tpu-getting-started/ (the M10-T007 fixture this suite
  reuses; do NOT add a parallel fixture)

Mission (full version in task spec):
Drive the same dry-run flow M10-T007 covers, but as an `eval_run`
record-producing suite: kg-nb round-trip, reviewer-gate firing,
decision-API approval round-trip, credentials-gate refusal. The
metric is the audit-grep guard (0 lines leaked to the kaggle CLI) +
the count of gates fired. No real Kaggle, no real Anthropic, no
real kernel push.
```

---

## Loop Prompt 5 — M13-T005 Reasoning-heavy benchmark

```
/goal Execute M13-T005 reasoning-heavy benchmark (5–10 fixed prompts; deterministic + rubric judges) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T005-reasoning-benchmark.md

Read also (background context):
- M13-T001 closeout
- src/worker/worker.py (the agent loop the benchmark drives)
- src/worker/routing.py (per-job-type routing)
- tools/kca/research_fetch.py (cached pages are an input to the
  research-brief prompt)
- docs/tasks/m5/M5-T002-browser-fetch-tool.md (research-brief precedent)
- .claude/skills/research-brief/SKILL.md (the skill this benchmark
  evaluates against)

Mission (full version in task spec):
Write 5–10 reasoning prompts spanning: research-brief from cached
pages, debug-a-worker-trace from a canned `agent_job_events` slice,
CV-result analysis from a frozen `experiment_runs` row, "should we
submit?" decision-gate rationale. Two judges per prompt: a
deterministic check (regex / JSON shape / key facts list) AND an
optional rubric-LLM call gated to `--route claude_haiku_4_5`
(cheapest) with a hard $0.05/prompt cap.
```

---

## Loop Prompt 6 — M13-T006 Model-route comparison harness

```
/goal Execute M13-T006 model-route comparison harness (Claude / GPT / local vLLM via litellm) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T006-model-route-comparison.md

Read also (background context):
- M13-T002 through M13-T005 closeouts
- src/worker/routing.py + ADR-0010 (model-routing)
- src/worker/local_model.py (vLLM / Ollama probe + fallback)
- docs/adr/0011-local-model-endpoints.md
- the project's auto-memory for local LLM endpoints (snorlax / may)

Mission (full version in task spec):
Wire the existing `tools/kca/eval/` suites so each can be invoked
with `--route claude_sonnet_4_6 | claude_haiku_4_5 | gpt_4o | local_vllm | mocked`.
For T006's own report, run a single shared sub-suite (a 5-case
slice of T002 + T005) across all five routes and write a row per
(suite × route) into `eval_results`. Hard cost cap (default
$0.50/run, env-tunable), hard time cap (default 600s), `--dry-run`
honoured. Refuse if `KCA_ALLOW_REMOTE != 1` for any non-local /
non-mocked route.
```

---

## Loop Prompt 7 — M13-T007 Metrics aggregator + `kca eval report`

```
/goal Execute M13-T007 metrics aggregator + `kca eval report` (JSON + Markdown snapshot) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T007-report-aggregator.md

Read also (background context):
- M13-T001 closeout (`eval_results` schema)
- M13-T002 through M13-T006 closeouts (the inputs the report rolls up)
- tools/kca/run.py (run-artifact layout precedent — the report's
  Markdown lands under `runs/m13-eval/<timestamp>/report.md`)
- docs/milestones/m9/final-review.md, docs/milestones/m10/final-review.md (the layout the
  report.md visual borrows from)

Mission (full version in task spec):
Implement `kca eval report --json` and `kca eval report --md`. The
report rolls up rows from `eval_results` for a given `eval_run_id`
(or the latest by default), groups by `suite × route`, and emits a
single JSON document + a single Markdown table. The Markdown is
human-diffable (git diff–friendly: stable row order, fixed-point
metric formatting). No new tables.
```

---

## Loop Prompt 8 — M13-T008 CI nightly cron + smoke / e2e tests

```
/goal Execute M13-T008 `.github/workflows/eval.yml` (nightly cron) + tests/test_m13_smoke.py + tests/test_m13_e2e.py until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T008-ci-and-tests.md

Read also (background context):
- M13-T001 through M13-T007 closeouts
- .github/workflows/test.yml (existing CI shape)
- tests/test_m9_smoke.py + tests/test_m9_e2e.py (closest pattern)
- tests/test_m10_e2e.py (the audit-grep regression sentinel pattern;
  M13's CI workflow inherits it)
- Issue #11 state check (must be CLOSED — same pre-req as M10-T007)

Mission (full version in task spec):
Add `tests/test_m13_smoke.py` (DB-gated; ~6 tests; the suites
register, the migration applied, the report aggregator emits a
parseable JSON). Add `tests/test_m13_e2e.py` (no-DB, no-creds,
no-net; runs each suite in `--route mocked` mode end-to-end against
checked-in fixtures, asserts `eval_results` rows in a sqlite tmpdir
DB). Add `.github/workflows/eval.yml` — scheduled nightly cron
(03:30 UTC) that runs `kca eval run --all --route mocked --json`,
uploads the JSON report as a workflow artefact, and `gh issue
comment`s the rolling diff against the previous nightly. Cron does
NOT touch real Kaggle / real LLM APIs.
```

---

## Loop Prompt 9 — M13-T009 Exit criteria + final review

```
/goal Execute M13-T009 M13 exit criteria validation + final review until docs/milestones/m13/final-review.md PASSes or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m13/M13-T009-m13-exit-criteria.md

Read also (background context):
- all M13 closeouts (T000–T008)
- docs/milestones/m10/final-review.md, docs/milestones/m9/final-review.md (layout
  precedents)
- `milestone-final-review` skill
- `worktree-milestone-pr` skill

Mission (full version in task spec):
Run the milestone validation matrix; call `milestone-final-review`
to write `docs/milestones/m13/final-review.md` mirroring the M9 / M10 layout.
After final review is written, `milestone-closeout` commits per Loop
Prompt (default), pushes the worktree branch, and opens the final
M13 PR against `main`.

Override note: this is the only Loop Prompt in M13 that calls
worktree-milestone-pr.
```

---

## GitHub issue / label workflow for M13

Each M13 task is filed as a GitHub issue using the `feature-work.yml`
form (or `test-gap.yml` for T008), labelled per task type. A
canonical M13 proposal issue is filed at planning close and is the
target of `decision:confirmed` for the milestone.

| Task | Issue labels at file time | Labels added by triage | Labels at merge |
|---|---|---|---|
| M13-T000 | `arch:`, `type:feature`, `ai:triage`, `area:eval`, `area:docs`, `decision:needed` | `decision:confirmed` + `ai:ready` after Discovery / Debate Gate transcripts attached | `ai:implementing` → close |
| M13-T001 | `type:feature`, `ai:triage`, `area:supabase`, `area:eval`, `area:cli` | `ai:ready` (after AC + owner) | `ai:implementing` → close |
| M13-T002 | `type:feature`, `ai:triage`, `area:eval`, `area:worker` | `ai:ready` | `ai:implementing` → close |
| M13-T003 | `type:feature`, `ai:triage`, `area:eval`, `area:kaggle` | `ai:ready` | `ai:implementing` → close |
| M13-T004 | `type:feature`, `ai:triage`, `area:eval`, `area:kaggle`, `area:testing` | `ai:ready` after M10-T007 fixture confirmed present | `ai:implementing` → close |
| M13-T005 | `type:feature`, `ai:triage`, `area:eval`, `area:worker` | `ai:ready` | `ai:implementing` → close |
| M13-T006 | `type:feature`, `ai:blocked`, `policy:approval-required`, `area:eval`, `area:routing`, `decision:needed` | `decision:confirmed` + `ai:ready` only after live-LLM budget cap confirmed on the M13 proposal issue | `ai:implementing` → close |
| M13-T007 | `type:feature`, `ai:triage`, `area:eval`, `area:docs` | `ai:ready` | `ai:implementing` → close |
| M13-T008 | `type:test-gap`, `ai:triage`, `area:testing`, `area:ci`, `area:eval` | `ai:ready` only after issue #11 confirmed CLOSED | `ai:implementing` → close |
| M13-T009 | `type:feature`, `ai:triage`, `area:release`, `area:docs` | `ai:ready` after T000–T008 closed | `ai:implementing` → close |

T000 and T006 are the only tasks that start with `decision:needed`.
T000 because it's `arch:` and the Discovery / Debate Gate verdict
is part of the decision record. T006 because it is the only Loop
Prompt that may make non-mocked, paid LLM calls and needs an
explicit budget cap recorded on the proposal issue.

T008 is gated on issue #11 being CLOSED — same posture as M10-T007.

The PR for each task uses `.github/pull_request_template.md`. T006's
PR is the ONLY M13 PR that may check the "External LLM call" box,
and must link the budget-cap comment from the proposal issue.

---

## Approval gates (summary)

| Gate | When it fires | Where the approval is recorded | Who can approve |
|---|---|---|---|
| `kaggle_submit` | Not used in M13 (out of scope) | n/a | n/a |
| `kernel_push` | Not used in M13 (out of scope) | n/a | n/a |
| `external_llm` (T006 only) | `kca eval run --route claude_* \| gpt_*` (any non-`local_vllm` / non-`mocked` route) | `human_decisions` row + comment on the M13 proposal issue | Project owner |
| `external_fetch` | Not used in M13 (cached pages only) | n/a | n/a |

T006's `external_llm` gate fires once per `eval run` invocation; the
M13 proposal issue carries the approved budget cap. If the budget
cap is exceeded mid-run, the harness aborts the remaining cases and
records `aborted_on_budget` in the run row.

---

## Required tests / evidence

- `python -m pytest tests/ services/decision_api/tests -v` — 0
  regressions vs M10 baseline + new `tests/test_m13_smoke.py` and
  `tests/test_m13_e2e.py` passing.
- `ruff check .` and `ruff format --check .` — clean.
- pnpm UI gates — unchanged from M10 baseline (M13 does not modify
  `ui/`); may SKIP if pnpm not on PATH.
- `kca eval list` shows ≥5 registered suites (tool-smoke,
  kaggle-replay-titanic, kaggle-replay-spaceship-titanic,
  kaggle-replay-house-prices, kernel-dryrun, reasoning).
- `kca eval run --all --route mocked --json > /tmp/m13-snapshot.json`
  exits 0, produces a non-empty JSON document, writes ≥1 row per
  registered suite into `eval_results`.
- `kca eval report --md` writes `runs/m13-eval/<timestamp>/report.md`;
  the report is committed to the M13 PR for posterity.
- `.github/workflows/eval.yml` validates locally with `actionlint`
  (or equivalent) and is wired to the nightly cron.
- M13-T006 closing issue carries the approved live-LLM budget cap
  AND the recorded `human_decisions` row.
- `docs/milestones/m13/final-review.md` exists and follows the M9 / M10 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt —
if any of these is true:

- T006 exceeds the approved live-LLM budget cap. The harness should
  abort cleanly; if it does not, the leak is a P0 bug.
- Any test in the validation suite regresses from green to red.
- The DSN, credentials, or `.env*` are accidentally printed in any
  log, audit row, eval report, or PR. Stop and rotate the credential.
- Any suite mistakenly calls real Kaggle or real-LLM endpoints when
  it should not. The audit-grep sentinel from M10-T007 must apply
  to every M13 suite: 0 lines for `kaggle competitions submit`,
  `kaggle kernels push`, `kaggle datasets create`, `kaggle datasets
  version` reach the kaggle CLI from any test or eval process.
- Issue #11 (dotenv leak) is reopened mid-milestone. Halt T008 work
  until #11 is green again.
- The Discovery / Debate Gate at T000 does not surface a load-bearing
  unknown (eval framework lock-in, schema decision, route comparison
  shape). Pause, request a human review of the three transcripts,
  do not advance to T001.

If M13 needs a new architectural decision mid-flight (e.g.
"reasoning benchmark needs its own DB table", "model-route harness
needs a new run-artefact shape"), pause and update ADR-0019 in a
new revision; do not advance to the next Loop Prompt with hidden
schema drift.

---

## Running on Arch Linux

```bash
# DB DSN (refresh container IP if `docker compose up` has rotated it)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local

# Optional, ONLY for T006 live-LLM route runs:
# export KCA_ALLOW_REMOTE=1
# export ANTHROPIC_API_KEY=...
# export OPENAI_API_KEY=...

# Per-prompt invocation (each Loop Prompt runs inside its own worktree
# per the milestone-loop-protocol §5 default):
claude "Use the milestone-loop-runner agent to execute M13-T000 from docs/milestones/m13/loop-prompts.md."
# ...repeat for M13-T001 … M13-T009.

# Milestone close:
claude "Use the milestone-closeout agent to finalize M13 — write docs/milestones/m13/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

DB calls (`psql`, `pytest` against `SUPABASE_DB_URL`, any `kca`
subcommand that reaches Supabase) need `dangerouslyDisableSandbox=true`.
T006 live-LLM route also needs sandbox bypass (network out to
`api.anthropic.com` / `api.openai.com` / the local vLLM hosts).
Cloud-LLM calls otherwise stay inside the sandbox.

---

## Human decisions needed before starting M13

These should be confirmed on the M13 proposal issue (file at end of
planning) before any T000 work begins:

1. **Entry pre-req.** M10 must be merged on `main`. Confirm
   `docs/milestones/m10/final-review.md` exists and reports PASS.
2. **CTF / hackathon eval scope.** Confirmed deferred to M13.1 /
   M13.2 — M11 (CTF) and M12 (Devpost) are not pre-reqs for M13.
3. **T006 live-LLM budget cap.** A hard $-per-run cap must be set
   before T006 may run any non-mocked route. Recommend $0.50 / run
   for the shared sub-suite; tunable via env. Default unattended
   nightly cron runs `--route mocked` only.
4. **Worktree.** Per-milestone worktree per
   `docs/milestone-loop-protocol.md` §5. Confirmed.
5. **Discovery / Debate Gate verdict on T000.** All three
   transcripts must land under `docs/evidence/m13/T000/discovery/`
   and the proposal issue must reach `decision:confirmed` before
   T001 starts.
6. **Failure handling.** If a suite fails mid-milestone, fix in
   place (the relevant Loop Prompt) and re-run — do not skip
   forward. Confirmed: same posture as M9 / M10.
