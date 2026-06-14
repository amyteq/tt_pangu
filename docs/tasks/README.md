# Task Specs

This directory contains task specification files for the `kaggle-code-agent` project.

Each file defines a discrete unit of work: goal, acceptance criteria, rules, expected output, and stop conditions.

## Folder organization

Task specs are grouped into one folder per category. Milestone tasks live in a
per-milestone folder; everything else falls into one of four non-milestone
buckets.

```text
docs/tasks/
  README.md                  # this file
  _templates/
    task.md                  # blank task-spec template
  m0/ m1/ ... m14/           # milestone task specs (one folder per milestone)
  housekeeping/              # repo-maintenance tasks not tied to a milestone
  competition-tracking/      # live-competition / leaderboard tracking tasks
  backlog/                   # current but not-yet-scheduled, non-milestone work
  uncategorized/             # tasks that could not be classified (explain below)
```

- **Milestone tasks** → `docs/tasks/m{N}/`. The folder name lowercases the
  milestone token and replaces `.` with `_` (so `M8.5` tasks live in `m8_5/`,
  `M9.3` tasks in `m9_3/`). The **filename keeps its original casing**
  (e.g. `m8_5/M8.5-T001-ci-repair.md`).
- **Housekeeping tasks** (docs reorganization, lint gates, CI chores not part of
  a milestone) → `docs/tasks/housekeeping/`.
- **Competition-tracking tasks** (per-competition submission tracking,
  leaderboard chasing) → `docs/tasks/competition-tracking/`.
- **Backlog tasks** (real work, not milestone-scoped, not yet scheduled) →
  `docs/tasks/backlog/`.
- **Uncategorized tasks** (cannot be confidently classified) →
  `docs/tasks/uncategorized/`, and add a one-line reason in the
  "Uncategorized tasks" section at the bottom of this file.

## Naming convention

```text
<milestone-folder>/<Milestone>-<sequence>-<short-description>.md
```

Example: `m0/M0-T001-project-baseline.md`

## How to execute a task

Point Claude Code at the spec with the `/goal` command:

```text
/goal Execute task from docs/tasks/m9/M9-T004-real-submission.md until its
acceptance criteria pass or its stop conditions trigger. Read the task file
fully first.
```

Read the spec's "Read these files first" list before editing, follow the
milestone loop protocol in `docs/milestone-loop-protocol.md`, and record
results / blockers in the closeout summary.

## Current tasks

| File | Milestone | Status | Description |
|---|---|---|---|
| `m0/M0-T001-project-baseline.md` | M0 | done | Repository baseline: docs, vocabulary, safety rules, test commands |
| `m1/M1-T000-legacy-tool-inventory.md` | M1 | done | Inventory and smoke-test legacy tools |
| `m1/M1-T001-kca-cli-skeleton.md` | M1 | done | `tools/kca/` CLI skeleton |
| `m1/M1-T002-notebook-conversion-wrappers.md` | M1 | done | `kca nb to-py / to-ipynb` wrappers |
| `m1/M1-T003-run-artifact-layout-and-smoke-tests.md` | M1 | done | `runs/<comp>/<run_id>/` layout + smoke tests |
| `m1/M1-T004-kaggle-remote-operation-approval-hooks.md` | M1 | done | Hooks + kca approval gate |
| `m1/M1-T005-m1-final-integration-review.md` | M1 | done | M1 exit criteria validation |
| `m2/M2-T001-schema-reconciliation.md` | M2 | done | Supabase schema alignment |
| `m2/M2-T002-local-supabase-dev.md` | M2 | done | Local Supabase dev workflow |
| `m2/M2-T003-python-db-layer.md` | M2 | done | `tools/kca/db.py` psycopg3 access layer |
| `m2/M2-T004-kca-run-db-writers.md` | M2 | done | `kca run *` commands DB-first |
| `m2/M2-T005-approval-event-recording.md` | M2 | done | Approval gate records `human_decisions` row |
| `m2/M2-T006-artifact-storage-adr.md` | M2 | done | ADR-0008 artifact storage local-first |
| `m2/M2-T007-db-smoke-tests.md` | M2 | done | DB smoke suite (5 tests) |
| `m2/M2-T008-final-integration-review.md` | M2 | done | M2 exit criteria validation |
| `m3/M3-T000-hotfix-kaggle-rename.md` | M3 | done | Rename `kaggle.py` → `kg.py` (import shadow fix) |
| `m3/M3-T001-migration-0003-job-events.md` | M3 | done | Migration 0003: job events schema + db.py job methods |
| `m3/M3-T002-workspace-management.md` | M3 | done | `kca workspace init/clean/list` git worktree isolation |
| `m3/M3-T003-worker-scaffold.md` | M3 | done | `src/worker/` scaffold: types, tools, budget |
| `m3/M3-T004-agent-worker-core.md` | M3 | done | `AgentWorker` core loop + budget enforcement |
| `m3/M3-T005-approval-gate-worker.md` | M3 | done | Approval-gate pause + `kca decisions` CLI |
| `m3/M3-T006-local-job-runner.md` | M3 | done | `scripts/run_job.py` local job runner |
| `m3/M3-T007-worker-smoke-tests.md` | M3 | done | `tests/test_worker_smoke.py` (6 tests, no API key) |
| `m3/M3-T008-m3-exit-criteria.md` | M3 | done | M3 exit criteria validation + `docs/milestones/m3/final-review.md` |
| `m4/M4-T000-pyproject-kca-entry-point.md` | M4 | done | `pyproject.toml` — pip-installable `kca` entry point |
| `m4/M4-T001-migration-0004-competition-repo.md` | M4 | done | Migration 0004: competition repo cols + experiments/runs/submissions tables |
| `m4/M4-T002-db-layer-competition-experiment.md` | M4 | done | DB layer: competition, experiment, run, submission functions |
| `m4/M4-T003-kca-competition-commands.md` | M4 | done | `kca competition register/clone/list` subcommands |
| `m4/M4-T004-workspace-repo-flag-and-kca-run.md` | M4 | done | `kca workspace init --repo` flag + `kca run init/record-metric/list` |
| `m4/M4-T005-run-job-competition-lifecycle.md` | M4 | done | `scripts/run_job.py` competition repo lifecycle (ADR-0009) |
| `m4/M4-T006-approval-gate-policy-resolution.md` | M4 | done | Configurable approval gate policy resolution (ADR-0006 full impl) |
| `m4/M4-T007-real-kaggle-cli-wiring.md` | M4 | done | Wire real `kaggle` CLI into `kca kaggle submit/push/download/watch` |
| `m4/M4-T008-tc1-titanic-end-to-end.md` | M4 | done | TC-1 Titanic end-to-end dry-run loop |
| `m4/M4-T009-m4-smoke-tests.md` | M4 | done | `tests/test_m4_smoke.py` (10 tests, no API/DB/credentials) |
| `m4/M4-T010-m4-exit-criteria.md` | M4 | done | M4 exit criteria validation + `docs/milestones/m4/final-review.md` |
| `m5/M5-T000-migration-0005-research-citations.md` | M5 | done | Migration 0005 — research_items extensions + research_citations table |
| `m5/M5-T001-db-layer-research.md` | M5 | done | DB layer — research / artifact / citation helpers |
| `m5/M5-T002-browser-fetch-tool.md` | M5 | done | `tools/kca/research_fetch.py` — lightweight HTTP + opt-in Playwright |
| `m5/M5-T003-kca-research-cli.md` | M5 | done | `kca research add/fetch/list/show/cite` CLI + `external_fetch` gate |
| `m5/M5-T004-kaggle-download-checksum.md` | M5 | done | `kca kaggle download --resume` + `kca kaggle verify` with sha256 manifest |
| `m5/M5-T005-resume-paused-jobs.md` | M5 | done | Resume paused jobs via `scripts/run_job.py --job-id` after approve |
| `m5/M5-T006-model-routing.md` | M5 | done | Model routing per job type (`src/worker/routing.py`, ADR-0010) |
| `m5/M5-T007-ci-github-actions.md` | M5 | done | `.github/workflows/test.yml` — no-db + live-db + lint |
| `m5/M5-T008-tc2-house-prices.md` | M5 | done | TC-2 House Prices end-to-end (RMSLE, two-experiment loop) |
| `m5/M5-T009-m5-smoke-tests.md` | M5 | done | `tests/test_m5_smoke.py` (10–12 tests) |
| `m5/M5-T010-m5-exit-criteria.md` | M5 | done | M5 exit criteria + `docs/milestones/m5/final-review.md` |
| `m6/M6-T000-migration-0006-reviews-spans.md` | M6 | proposed | Migration 0006 — agent_reviews + agent_telemetry_spans + agent_jobs.otel_* |
| `m6/M6-T001-db-layer-reviews-telemetry.md` | M6 | proposed | DB layer — review + telemetry helpers |
| `m6/M6-T002-local-model-layer.md` | M6 | proposed | `src/worker/local_model.py` — endpoint config + probe + LiteLLM dispatch (ADR-0011) |
| `m6/M6-T003-env-example-update.md` | M6 | proposed | `env.example` — snorlax/may endpoints + reviewer + OTEL knobs |
| `m6/M6-T004-reviewer-worker.md` | M6 | proposed | `src/worker/reviewer.py` + sync-gate integration (ADR-0012) |
| `m6/M6-T005-otel-instrumentation.md` | M6 | proposed | OTEL instrumentation: console + SQLite + Supabase exporters (ADR-0013) |
| `m6/M6-T006-local-model-job-types.md` | M6 | proposed | `log_triage` / `summarise` job types + `kca local triage` |
| `m6/M6-T007-kca-review-cli.md` | M6 | proposed | `kca review list / show / run` CLI |
| `m6/M6-T008-tc3-spaceship-titanic.md` | M6 | proposed | TC-3 Spaceship Titanic end-to-end with reviewer-gate |
| `m6/M6-T009-m6-smoke-tests.md` | M6 | proposed | `tests/test_m6_smoke.py` (12–14 tests) |
| `m6/M6-T010-m6-exit-criteria.md` | M6 | proposed | M6 exit criteria + `docs/milestones/m6/final-review.md` |
| `m7/M7-T000-ci-workflows-repair.md` | M7 | backfilled | CI repair — audit `.github/workflows/` and make `no-db` + `lint` jobs green |
| `m7/M7-T001-skill-loader.md` | M7 | backfilled | Skill loader — `.kca/skills/<name>/SKILL.md` + YAML frontmatter + `$arg` substitution |
| `m7/M7-T002-command-registry.md` | M7 | backfilled | Command registry — declarative subcommand registration |
| `m7/M7-T003-tool-registry.md` | M7 | backfilled | Tool registry — tool metadata, approval labels, sandbox metadata |
| `m7/M7-T004-permission-policy.md` | M7 | backfilled | Permission policy layer — allow/ask/deny from YAML/JSON policy records |
| `m7/M7-T005-kca-skill-cli.md` | M7 | backfilled | `kca skill list / show / run [--dry-run]` CLI |
| `m7/M7-T006-audit-logging.md` | M7 | backfilled | Audit logging — record every tool execution + policy decision |
| `m7/M7-T007-seed-skills.md` | M7 | backfilled | Seed `.kca/skills/` with 4 workflow recipes |
| `m7/M7-T008-m7-smoke-tests.md` | M7 | backfilled | `tests/test_m7_smoke.py` (12–15 tests, no credentials) |
| `m7/M7-T009-architecture-doc.md` | M7 | backfilled | Architecture doc `docs/architecture/kca-cli-architecture.md` |
| `m7/M7-T010-m7-exit-criteria.md` | M7 | backfilled | M7 exit criteria + `docs/milestones/m7/final-review.md` |
| `m8/M8-T000-ui-stack-adr-scaffold.md` | M8 | backfilled | UI stack ADR + scaffold (Vite + React + TS + Tailwind) |
| `m8/M8-T001-agent-tool-audit-migration.md` | M8 | backfilled | Migration 0007 — `agent_tool_audit` table + view; dual-write JSONL/DB |
| `m8/M8-T002-skill-schema-gate.md` | M8 | backfilled | JSON-Schema gate on SKILL.md frontmatter; retire `_test_fixture` skill |
| `m8/M8-T003-skill-worker-wiring.md` | M8 | backfilled | Skill → worker wiring; `ToolSpec` enforcement in `worker._tool_call` |
| `m8/M8-T004-ui-app-shell.md` | M8 | backfilled | UI app shell — layout, nav, theming, read-only Supabase client |
| `m8/M8-T005-ui-dashboard.md` | M8 | backfilled | Dashboard page — projects / competitions / in-flight runs / recent decisions |
| `m8/M8-T006-ui-run-timeline.md` | M8 | backfilled | Run Timeline page — OTEL span swim-lane + event log |
| `m8/M8-T007-ui-experiments-runs.md` | M8 | backfilled | Experiments / Runs page — sortable table, metric drill-down |
| `m8/M8-T008-ui-research.md` | M8 | backfilled | Research page — citations, trust labels, source links |
| `m8/M8-T009-ui-approval-inbox.md` | M8 | backfilled | Approval Inbox + Decision Gate — Approve / Reject / Ask-improve |
| `m8/M8-T010-ui-artifact-browser.md` | M8 | backfilled | Artifact Browser — listing + small-file preview (read-only) |
| `m8/M8-T011-ci-ui-build.md` | M8 | backfilled | CI — UI build / lint / typecheck job; gate `live-db` on forks |
| `m8/M8-T012-smoke-tests-playwright.md` | M8 | backfilled | `tests/test_m8_smoke.py` + minimal Playwright smoke |
| `m8/M8-T013-m8-architecture-doc.md` | M8 | backfilled | `docs/architecture/m8-ui-shell.md` — data flow, auth, gate semantics |
| `m8/M8-T014-m8-exit-criteria.md` | M8 | backfilled | M8 exit criteria + `docs/milestones/m8/final-review.md` + `docs/milestones/m8/handoff.md` |
| `m8_5/M8.5-T001-ci-repair.md` | M8.5 | done | CI repair — Python deps + `kca skill` registration + pnpm workspace (PR #4) |
| `m8_5/M8.5-T002-engineering-practice-github-interface.md` | M8.5 | done | Engineering practice docs + GitHub Issues/PR/labels collaboration + agents/skills (PR #5) |
| `m8_5/M8.5-T003-m9-planning-only.md` | M8.5 | done | M9 planning only — drafted `docs/milestones/m9/loop-prompts.md` + 9 M9 task specs (PR #6) |
| `m9/M9-T000-kaggle-credentials.md` | M9 | proposed | Kaggle credentials + competition registration (no real submit, no secret print) |
| `m9/M9-T001-data-download.md` | M9 | proposed | Download Spaceship Titanic data, verify sha256 manifest, commit `manifest.json` only |
| `m9/M9-T002-baseline-loop.md` | M9 | proposed | Worker baseline LR loop → CV score + staged `submission.csv` (no submit) |
| `m9/M9-T003-reviewer-approval-gate.md` | M9 | proposed | Reviewer gate fires; decision_api / UI Approval Inbox surface the pending submit |
| `m9/M9-T004-real-submission.md` | M9 | proposed | **ONE** real Kaggle submit under explicit human approval; record LB score |
| `m9/M9-T005-second-experiment.md` | M9 | proposed | HGB + feature engineering — local only; no second real submission |
| `m9/M9-T006-regression-assertions.md` | M9 | proposed | CV ≥ 0.78 (LR), ≥ 0.80 (HGB); LB recorded; HGB > LR |
| `m9/M9-T007-e2e-dryrun-test.md` | M9 | proposed | `tests/test_m9_e2e.py` dry-run path (no credentials, no network, no DB) |
| `m9/M9-T008-m9-exit-criteria.md` | M9 | proposed | M9 exit criteria + `docs/milestones/m9/final-review.md` + M9 PR |
| `m11/M11-T000-discovery-debate-gate.md` | M11 | done | Discovery / Debate Gate — 3 subagent reports for CTF data model + approval ops |
| `m11/M11-T001-ctf-schema-db.md` | M11 | done | `supabase/migrations/0008_m11_ctf.sql` + `src/db/ctf.py` helpers + ADR-0016 |
| `m11/M11-T002-approval-gates.md` | M11 | done | `challenge_run` / `flag_submit` / `network_egress` ops + reviewer-gate wiring + ADR-0017 |
| `m11/M11-T003-kca-ctf-cli.md` | M11 | done | `tools/kca/ctf.py` 12 subcommands across 5 namespaces + COMMANDS.md |
| `m11/M11-T004-frozen-challenges.md` | M11 | done | Frozen past-event bundle (web-1 + crypto-1 bespoke fixtures) + licensing brief |
| `m11/M11-T005-local-solve-loop.md` | M11 | done | Agent loop solves web + crypto locally; 2 `ctf_attempts(accepted=true)` in cloud |
| `m11/M11-T006-reviewer-gate.md` | M11 | done | Reviewer-gate round-trips for `challenge_run` + `flag_submit`; `network_egress` reject smoke |
| `m11/M11-T007-live-flag-submission.md` | M11 | deferred | ONE real flag submission to live CTFtime event (SKIP-BLOCKED — human action required) |
| `m11/M11-T008-e2e-dryrun-test.md` | M11 | done | `tests/test_m11_e2e.py` (8/8) + `tests/test_m11_smoke.py` (7/7) |
| `m11/M11-T009-m11-exit-criteria.md` | M11 | done | M11 exit criteria + `docs/milestones/m11/final-review.md` + handoff + PR |
| `m12/M12-T000-survey-and-pick-target.md` | M12 | done | Survey 2–3 Devpost/hackathon candidates; human picks target slug h01 |
| `m12/M12-T001-discovery-debate-gate.md` | M12 | done | Discovery/Debate Gate on competition-policy generalization; ADR-0018 |
| `m12/M12-T002-schema-and-policy.md` | M12 | done | Migration 0009 — competition_type / teams / deadline; policy resolver refactor |
| `m12/M12-T003-devpost-adapter.md` | M12 | done | `tools/kca/devpost.py` + `kca devpost register/fetch/info` (READ_ONLY) |
| `m12/M12-T004-hackathon-skill.md` | M12 | done | hackathon-experiment-loop skill + hackathon-runner.yaml + submission_checklist tool |
| `m12/M12-T005-ui-pages.md` | M12 | done | UI: HackathonDeadline + SubmissionChecklist pages + routes + tests |
| `m12/M12-T006-end-to-end-local.md` | M12 | done | Worker runs hackathon flow end-to-end; submission_pack produced (hand-driven) |
| `m12/M12-T007-real-submit.md` | M12 | done | Reviewer gate fired; cmd_submit added (credentials-gated); real submit DEFERRED |
| `m12/M12-T008-regression-tests.md` | M12 | done | `tests/test_m12_e2e.py` (6 tests) + `tests/test_m12_smoke.py` (5 PASS + 2 XFAIL) |
| `m12/M12-T009-final-review.md` | M12 | done | M12 exit criteria + `docs/milestones/m12/final-review.md` + closeout |
| `m13/M13-T000-eval-architecture.md` | M13 | done | `arch:` Discovery/Debate Gate; ADR-0019 (renumbered from 0016 — M11 took 0016/0017 + M12 took 0018); regression-suite architecture doc |
| `m13/M13-T001-migration-and-cli.md` | M13 | done | Migration **0010_m13_eval.sql** (renumbered from 0008 — M11 took 0008 and M12 took 0009); 8 DB helpers; `kca eval` CLI scaffold |
| `m13/M13-T002-tool-smoke-suite.md` | M13 | done | `tool-smoke` suite; 10 cases; deterministic; audit-grep clean |
| `m13/M13-T003-kaggle-replay-suite.md` | M13 | done | 3 Kaggle replay suites (titanic, spaceship-titanic, house-prices); offline fixtures; deterministic |
| `m13/M13-T004-notebook-kernel-dryrun-suite.md` | M13 | done | `kernel-dryrun` suite; 4 cases; credentials-gate refusal verified; M10 fixture coexistence |
| `m13/M13-T005-reasoning-benchmark.md` | M13 | done | `reasoning` suite; 5 cases; deterministic shape-check judge |
| `m13/M13-T006-model-route-comparison.md` | M13 | done | 5 routes wired; paid-route refusal; `--route-compare` 25 rows; no money spent |
| `m13/M13-T007-report-aggregator.md` | M13 | done | Aggregator + `kca eval report` (JSON + MD); canonical snapshot committed |
| `m13/M13-T008-ci-and-tests.md` | M13 | done | CI nightly cron; `tests/test_m13_smoke.py` (6); `tests/test_m13_e2e.py` (6); tracking issue #47 |
| `m13/M13-T009-m13-exit-criteria.md` | M13 | done | M13 exit criteria + `docs/milestones/m13/final-review.md` + tracking-doc updates + PR |

> **Convention (M0–M6, M8.5 onward):** Every milestone uses the
> **double-layer** pattern — `docs/m{N}-loop-prompts.md` for the per-loop
> wrappers and `docs/tasks/M{N}-T*-*.md` for each task's full spec
> (goal, read list, acceptance criteria, stop condition). Loop prompts
> reference the shared `docs/milestone-loop-protocol.md` for boilerplate
> instead of inlining it.
>
> **M7 / M8 are being backfilled** — original convention inlined the
> task spec into the Loop Prompt block. Task specs in this directory
> with the `backfilled` status were extracted from the corresponding
> Loop Prompt; the loop prompts file remains the historical record.

## How to use these files

1. Read the task spec before starting any work.
2. Follow the "Read these files first" list in the spec.
3. Return a plan and wait for human approval before editing any files.
4. Record results and blockers in the post-edit summary.
5. Update the task status when complete.

## Uncategorized tasks

None at present. When a task lands in `docs/tasks/uncategorized/`, add a row
here with the filename and a one-line reason it could not be classified.

| File | Reason |
|---|---|
| _(none)_ | — |

## Source of truth

Task specs live in this repository. They are the authoritative scope definition for any Claude Code session, ChatGPT session, Cursor session, or other AI tool working on this project. Hidden AI memory does not override the task spec.

## Related docs

- `docs/milestones/README.md` — high-level product plan (M0 through M14) with suggested task sequencing
- `docs/milestone-loop-protocol.md` — shared rules for executing milestone loop prompts
- `docs/architecture/platform-vs-runtime-agents.md` — terminology: two meanings of "code agent"
- `AGENTS.md` — cross-tool development rules
- `CLAUDE.md` — Claude Code-specific rules and safety boundaries
