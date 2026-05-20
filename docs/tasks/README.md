# Task Specs

This directory contains task specification files for the `kaggle-code-agent` project.

Each file defines a discrete unit of work: goal, acceptance criteria, rules, expected output, and stop conditions.

## Naming convention

```
<milestone>-<sequence>-<short-description>.md
```

Example: `M0-T001-project-baseline.md`

## Current tasks

| File | Milestone | Status | Description |
|---|---|---|---|
| `M0-T001-project-baseline.md` | M0 | done | Repository baseline: docs, vocabulary, safety rules, test commands |
| `M1-T000-legacy-tool-inventory.md` | M1 | done | Inventory and smoke-test legacy tools |
| `M1-T001-kca-cli-skeleton.md` | M1 | done | `tools/kca/` CLI skeleton |
| `M1-T002-notebook-conversion-wrappers.md` | M1 | done | `kca nb to-py / to-ipynb` wrappers |
| `M1-T003-run-artifact-layout-and-smoke-tests.md` | M1 | done | `runs/<comp>/<run_id>/` layout + smoke tests |
| `M1-T004-kaggle-remote-operation-approval-hooks.md` | M1 | done | Hooks + kca approval gate |
| `M1-T005-m1-final-integration-review.md` | M1 | done | M1 exit criteria validation |
| `M2-T001-schema-reconciliation.md` | M2 | done | Supabase schema alignment |
| `M2-T002-local-supabase-dev.md` | M2 | done | Local Supabase dev workflow |
| `M2-T003-python-db-layer.md` | M2 | done | `tools/kca/db.py` psycopg3 access layer |
| `M2-T004-kca-run-db-writers.md` | M2 | done | `kca run *` commands DB-first |
| `M2-T005-approval-event-recording.md` | M2 | done | Approval gate records `human_decisions` row |
| `M2-T006-artifact-storage-adr.md` | M2 | done | ADR-0008 artifact storage local-first |
| `M2-T007-db-smoke-tests.md` | M2 | done | DB smoke suite (5 tests) |
| `M2-T008-final-integration-review.md` | M2 | done | M2 exit criteria validation |
| `M3-T000-hotfix-kaggle-rename.md` | M3 | done | Rename `kaggle.py` → `kg.py` (import shadow fix) |
| `M3-T001-migration-0003-job-events.md` | M3 | done | Migration 0003: job events schema + db.py job methods |
| `M3-T002-workspace-management.md` | M3 | done | `kca workspace init/clean/list` git worktree isolation |
| `M3-T003-worker-scaffold.md` | M3 | done | `src/worker/` scaffold: types, tools, budget |
| `M3-T004-agent-worker-core.md` | M3 | done | `AgentWorker` core loop + budget enforcement |
| `M3-T005-approval-gate-worker.md` | M3 | done | Approval-gate pause + `kca decisions` CLI |
| `M3-T006-local-job-runner.md` | M3 | done | `scripts/run_job.py` local job runner |
| `M3-T007-worker-smoke-tests.md` | M3 | done | `tests/test_worker_smoke.py` (6 tests, no API key) |
| `M3-T008-m3-exit-criteria.md` | M3 | done | M3 exit criteria validation + `docs/m3-final-review.md` |
| `M4-T000-pyproject-kca-entry-point.md` | M4 | done | `pyproject.toml` — pip-installable `kca` entry point |
| `M4-T001-migration-0004-competition-repo.md` | M4 | done | Migration 0004: competition repo cols + experiments/runs/submissions tables |
| `M4-T002-db-layer-competition-experiment.md` | M4 | done | DB layer: competition, experiment, run, submission functions |
| `M4-T003-kca-competition-commands.md` | M4 | done | `kca competition register/clone/list` subcommands |
| `M4-T004-workspace-repo-flag-and-kca-run.md` | M4 | done | `kca workspace init --repo` flag + `kca run init/record-metric/list` |
| `M4-T005-run-job-competition-lifecycle.md` | M4 | done | `scripts/run_job.py` competition repo lifecycle (ADR-0009) |
| `M4-T006-approval-gate-policy-resolution.md` | M4 | done | Configurable approval gate policy resolution (ADR-0006 full impl) |
| `M4-T007-real-kaggle-cli-wiring.md` | M4 | done | Wire real `kaggle` CLI into `kca kaggle submit/push/download/watch` |
| `M4-T008-tc1-titanic-end-to-end.md` | M4 | done | TC-1 Titanic end-to-end dry-run loop |
| `M4-T009-m4-smoke-tests.md` | M4 | done | `tests/test_m4_smoke.py` (10 tests, no API/DB/credentials) |
| `M4-T010-m4-exit-criteria.md` | M4 | done | M4 exit criteria validation + `docs/m4-final-review.md` |
| `M5-T000-migration-0005-research-citations.md` | M5 | done | Migration 0005 — research_items extensions + research_citations table |
| `M5-T001-db-layer-research.md` | M5 | done | DB layer — research / artifact / citation helpers |
| `M5-T002-browser-fetch-tool.md` | M5 | done | `tools/kca/research_fetch.py` — lightweight HTTP + opt-in Playwright |
| `M5-T003-kca-research-cli.md` | M5 | done | `kca research add/fetch/list/show/cite` CLI + `external_fetch` gate |
| `M5-T004-kaggle-download-checksum.md` | M5 | done | `kca kaggle download --resume` + `kca kaggle verify` with sha256 manifest |
| `M5-T005-resume-paused-jobs.md` | M5 | done | Resume paused jobs via `scripts/run_job.py --job-id` after approve |
| `M5-T006-model-routing.md` | M5 | done | Model routing per job type (`src/worker/routing.py`, ADR-0010) |
| `M5-T007-ci-github-actions.md` | M5 | done | `.github/workflows/test.yml` — no-db + live-db + lint |
| `M5-T008-tc2-house-prices.md` | M5 | done | TC-2 House Prices end-to-end (RMSLE, two-experiment loop) |
| `M5-T009-m5-smoke-tests.md` | M5 | done | `tests/test_m5_smoke.py` (10–12 tests) |
| `M5-T010-m5-exit-criteria.md` | M5 | done | M5 exit criteria + `docs/m5-final-review.md` |
| `M6-T000-migration-0006-reviews-spans.md` | M6 | proposed | Migration 0006 — agent_reviews + agent_telemetry_spans + agent_jobs.otel_* |
| `M6-T001-db-layer-reviews-telemetry.md` | M6 | proposed | DB layer — review + telemetry helpers |
| `M6-T002-local-model-layer.md` | M6 | proposed | `src/worker/local_model.py` — endpoint config + probe + LiteLLM dispatch (ADR-0011) |
| `M6-T003-env-example-update.md` | M6 | proposed | `env.example` — snorlax/may endpoints + reviewer + OTEL knobs |
| `M6-T004-reviewer-worker.md` | M6 | proposed | `src/worker/reviewer.py` + sync-gate integration (ADR-0012) |
| `M6-T005-otel-instrumentation.md` | M6 | proposed | OTEL instrumentation: console + SQLite + Supabase exporters (ADR-0013) |
| `M6-T006-local-model-job-types.md` | M6 | proposed | `log_triage` / `summarise` job types + `kca local triage` |
| `M6-T007-kca-review-cli.md` | M6 | proposed | `kca review list / show / run` CLI |
| `M6-T008-tc3-spaceship-titanic.md` | M6 | proposed | TC-3 Spaceship Titanic end-to-end with reviewer-gate |
| `M6-T009-m6-smoke-tests.md` | M6 | proposed | `tests/test_m6_smoke.py` (12–14 tests) |
| `M6-T010-m6-exit-criteria.md` | M6 | proposed | M6 exit criteria + `docs/m6-final-review.md` |

## How to use these files

1. Read the task spec before starting any work.
2. Follow the "Read these files first" list in the spec.
3. Return a plan and wait for human approval before editing any files.
4. Record results and blockers in the post-edit summary.
5. Update the task status when complete.

## Source of truth

Task specs live in this repository. They are the authoritative scope definition for any Claude Code session, ChatGPT session, Cursor session, or other AI tool working on this project. Hidden AI memory does not override the task spec.

## Related docs

- `docs/milestones.md` — high-level product plan (M0 through M10) with suggested task sequencing
- `docs/architecture/platform-vs-runtime-agents.md` — terminology: two meanings of "code agent"
- `AGENTS.md` — cross-tool development rules
- `CLAUDE.md` — Claude Code-specific rules and safety boundaries
