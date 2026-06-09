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
| `M7-T000-ci-workflows-repair.md` | M7 | backfilled | CI repair — audit `.github/workflows/` and make `no-db` + `lint` jobs green |
| `M7-T001-skill-loader.md` | M7 | backfilled | Skill loader — `.kca/skills/<name>/SKILL.md` + YAML frontmatter + `$arg` substitution |
| `M7-T002-command-registry.md` | M7 | backfilled | Command registry — declarative subcommand registration |
| `M7-T003-tool-registry.md` | M7 | backfilled | Tool registry — tool metadata, approval labels, sandbox metadata |
| `M7-T004-permission-policy.md` | M7 | backfilled | Permission policy layer — allow/ask/deny from YAML/JSON policy records |
| `M7-T005-kca-skill-cli.md` | M7 | backfilled | `kca skill list / show / run [--dry-run]` CLI |
| `M7-T006-audit-logging.md` | M7 | backfilled | Audit logging — record every tool execution + policy decision |
| `M7-T007-seed-skills.md` | M7 | backfilled | Seed `.kca/skills/` with 4 workflow recipes |
| `M7-T008-m7-smoke-tests.md` | M7 | backfilled | `tests/test_m7_smoke.py` (12–15 tests, no credentials) |
| `M7-T009-architecture-doc.md` | M7 | backfilled | Architecture doc `docs/architecture/kca-cli-architecture.md` |
| `M7-T010-m7-exit-criteria.md` | M7 | backfilled | M7 exit criteria + `docs/m7-final-review.md` |
| `M8-T000-ui-stack-adr-scaffold.md` | M8 | backfilled | UI stack ADR + scaffold (Vite + React + TS + Tailwind) |
| `M8-T001-agent-tool-audit-migration.md` | M8 | backfilled | Migration 0007 — `agent_tool_audit` table + view; dual-write JSONL/DB |
| `M8-T002-skill-schema-gate.md` | M8 | backfilled | JSON-Schema gate on SKILL.md frontmatter; retire `_test_fixture` skill |
| `M8-T003-skill-worker-wiring.md` | M8 | backfilled | Skill → worker wiring; `ToolSpec` enforcement in `worker._tool_call` |
| `M8-T004-ui-app-shell.md` | M8 | backfilled | UI app shell — layout, nav, theming, read-only Supabase client |
| `M8-T005-ui-dashboard.md` | M8 | backfilled | Dashboard page — projects / competitions / in-flight runs / recent decisions |
| `M8-T006-ui-run-timeline.md` | M8 | backfilled | Run Timeline page — OTEL span swim-lane + event log |
| `M8-T007-ui-experiments-runs.md` | M8 | backfilled | Experiments / Runs page — sortable table, metric drill-down |
| `M8-T008-ui-research.md` | M8 | backfilled | Research page — citations, trust labels, source links |
| `M8-T009-ui-approval-inbox.md` | M8 | backfilled | Approval Inbox + Decision Gate — Approve / Reject / Ask-improve |
| `M8-T010-ui-artifact-browser.md` | M8 | backfilled | Artifact Browser — listing + small-file preview (read-only) |
| `M8-T011-ci-ui-build.md` | M8 | backfilled | CI — UI build / lint / typecheck job; gate `live-db` on forks |
| `M8-T012-smoke-tests-playwright.md` | M8 | backfilled | `tests/test_m8_smoke.py` + minimal Playwright smoke |
| `M8-T013-m8-architecture-doc.md` | M8 | backfilled | `docs/architecture/m8-ui-shell.md` — data flow, auth, gate semantics |
| `M8-T014-m8-exit-criteria.md` | M8 | backfilled | M8 exit criteria + `docs/m8-final-review.md` + `docs/handoffs/m8-handoff.md` |
| `M8.5-T001-ci-repair.md` | M8.5 | done | CI repair — Python deps + `kca skill` registration + pnpm workspace (PR #4) |
| `M8.5-T002-engineering-practice-github-interface.md` | M8.5 | done | Engineering practice docs + GitHub Issues/PR/labels collaboration + agents/skills (PR #5) |
| `M8.5-T003-m9-planning-only.md` | M8.5 | done | M9 planning only — drafted `docs/m9-loop-prompts.md` + 9 M9 task specs (PR #6) |
| `M9-T000-kaggle-credentials.md` | M9 | proposed | Kaggle credentials + competition registration (no real submit, no secret print) |
| `M9-T001-data-download.md` | M9 | proposed | Download Spaceship Titanic data, verify sha256 manifest, commit `manifest.json` only |
| `M9-T002-baseline-loop.md` | M9 | proposed | Worker baseline LR loop → CV score + staged `submission.csv` (no submit) |
| `M9-T003-reviewer-approval-gate.md` | M9 | proposed | Reviewer gate fires; decision_api / UI Approval Inbox surface the pending submit |
| `M9-T004-real-submission.md` | M9 | proposed | **ONE** real Kaggle submit under explicit human approval; record LB score |
| `M9-T005-second-experiment.md` | M9 | proposed | HGB + feature engineering — local only; no second real submission |
| `M9-T006-regression-assertions.md` | M9 | proposed | CV ≥ 0.78 (LR), ≥ 0.80 (HGB); LB recorded; HGB > LR |
| `M9-T007-e2e-dryrun-test.md` | M9 | proposed | `tests/test_m9_e2e.py` dry-run path (no credentials, no network, no DB) |
| `M9-T008-m9-exit-criteria.md` | M9 | proposed | M9 exit criteria + `docs/m9-final-review.md` + M9 PR |
| `M11-T000-discovery-debate-gate.md` | M11 | done | Discovery / Debate Gate — 3 subagent reports for CTF data model + approval ops |
| `M11-T001-ctf-schema-db.md` | M11 | done | `supabase/migrations/0008_m11_ctf.sql` + `src/db/ctf.py` helpers + ADR-0016 |
| `M11-T002-approval-gates.md` | M11 | done | `challenge_run` / `flag_submit` / `network_egress` ops + reviewer-gate wiring + ADR-0017 |
| `M11-T003-kca-ctf-cli.md` | M11 | done | `tools/kca/ctf.py` 12 subcommands across 5 namespaces + COMMANDS.md |
| `M11-T004-frozen-challenges.md` | M11 | done | Frozen past-event bundle (web-1 + crypto-1 bespoke fixtures) + licensing brief |
| `M11-T005-local-solve-loop.md` | M11 | done | Agent loop solves web + crypto locally; 2 `ctf_attempts(accepted=true)` in cloud |
| `M11-T006-reviewer-gate.md` | M11 | done | Reviewer-gate round-trips for `challenge_run` + `flag_submit`; `network_egress` reject smoke |
| `M11-T007-live-flag-submission.md` | M11 | deferred | ONE real flag submission to live CTFtime event (SKIP-BLOCKED — human action required) |
| `M11-T008-e2e-dryrun-test.md` | M11 | done | `tests/test_m11_e2e.py` (8/8) + `tests/test_m11_smoke.py` (7/7) |
| `M11-T009-m11-exit-criteria.md` | M11 | done | M11 exit criteria + `docs/m11-final-review.md` + handoff + PR |
| `M12-T000-survey-and-pick-target.md` | M12 | done | Survey 2–3 Devpost/hackathon candidates; human picks target slug h01 |
| `M12-T001-discovery-debate-gate.md` | M12 | done | Discovery/Debate Gate on competition-policy generalization; ADR-0018 |
| `M12-T002-schema-and-policy.md` | M12 | done | Migration 0009 — competition_type / teams / deadline; policy resolver refactor |
| `M12-T003-devpost-adapter.md` | M12 | done | `tools/kca/devpost.py` + `kca devpost register/fetch/info` (READ_ONLY) |
| `M12-T004-hackathon-skill.md` | M12 | done | hackathon-experiment-loop skill + hackathon-runner.yaml + submission_checklist tool |
| `M12-T005-ui-pages.md` | M12 | done | UI: HackathonDeadline + SubmissionChecklist pages + routes + tests |
| `M12-T006-end-to-end-local.md` | M12 | done | Worker runs hackathon flow end-to-end; submission_pack produced (hand-driven) |
| `M12-T007-real-submit.md` | M12 | done | Reviewer gate fired; cmd_submit added (credentials-gated); real submit DEFERRED |
| `M12-T008-regression-tests.md` | M12 | done | `tests/test_m12_e2e.py` (6 tests) + `tests/test_m12_smoke.py` (5 PASS + 2 XFAIL) |
| `M12-T009-final-review.md` | M12 | done | M12 exit criteria + `docs/m12-final-review.md` + closeout |

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

## Source of truth

Task specs live in this repository. They are the authoritative scope definition for any Claude Code session, ChatGPT session, Cursor session, or other AI tool working on this project. Hidden AI memory does not override the task spec.

## Related docs

- `docs/milestones.md` — high-level product plan (M0 through M10) with suggested task sequencing
- `docs/architecture/platform-vs-runtime-agents.md` — terminology: two meanings of "code agent"
- `AGENTS.md` — cross-tool development rules
- `CLAUDE.md` — Claude Code-specific rules and safety boundaries
