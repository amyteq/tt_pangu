# kaggle-code-agent (kca)

A hybrid human + AI workbench for competitive programming: Kaggle competitions, authorized CTF/lab challenges, Devpost hackathons, and similar code contests.

The platform is **local-first and audit-first**. Every research note, experiment, code change, test result, approval, and submission is traceable.

## Two meanings of "code agent"

This project uses two related but distinct concepts.

**Platform-development coding agents** are external AI tools — Claude Code (primary), ChatGPT, Cursor — used to build this repository. They write source code, update docs, run local tests, and open PRs under human supervision.

**Runtime competition code agents** are agents launched by the finished platform to help a human user compete. Initial runtime: Claude Agent SDK in an isolated Python worker. Future: model router for Claude (Sonnet/Opus), GPT-style models, and local vLLM/Ollama models.

See `docs/architecture/platform-vs-runtime-agents.md` for the full breakdown.

## Source of truth

**GitHub repo + Claude Code + CI + Supabase migrations.**

AI tools do not share hidden memory reliably across sessions or products. All decisions, architecture, task specs, and safety rules must live in repo files. Claude Code is the primary development environment for all product layers (CLI, backend, UI shell, worker).

Key files:
- `PROJECT_STATE.md` — current project snapshot and open decisions
- `AGENTS.md` — cross-tool instructions for ChatGPT, Codex, Cursor, and other agents
- `CLAUDE.md` — Claude Code-specific instructions and safety boundaries
- `docs/adr/` — architecture decision records
- `docs/milestones/README.md` — product plan from M0 through M14

## Repository layout

```
CLAUDE.md                    Claude Code project instructions
AGENTS.md                    Cross-tool agent instructions
PROJECT_STATE.md             Current project snapshot
INSTALL.md                   Local install, configure, and run guide

.claude/
  settings.json              Permissions, sandbox, hooks
  hooks/                     Pre/post tool safety and audit hooks
  agents/                    Subagents: researcher, experimenter, reviewer, safety-guard

.kca/
  skills/                    Agent workflow recipes (SKILL.md files)
  tools/tools.yaml           Tool registry with permission labels
  permissions/               Policy profiles (default, permissive-dev, competition-runner)

docs/
  milestones.md              Product plan M0–M14
  architecture.md            Component architecture overview
  architecture/
    kca-cli-architecture.md  Commands vs Skills vs Tools vs Jobs (M7)
    model-routing.md         Model routing tiers and logging policy
    platform-vs-runtime-agents.md  Two meanings of "code agent"
  adr/                       Architecture decision records
  tasks/                     Task specifications (M0-T001, M1-T001, ...)
  testing.md                 Test commands and current blockers
  testing/                   Competition-level regression test cases
  meeting-notes/             Summarized decisions and discussions

competitions/                Per-competition workspaces (docs + agent/kernel code)
  README.md                  Active competitions dashboard
  _templates/                Reusable per-competition doc templates
  _shared/                   Cross-competition insights, common bugs, migration notes
  nvidia-nemotron/           NVIDIA Nemotron Model Reasoning Challenge (nemo)
  orbit-wars/                Kaggle Orbit Wars (orbit) agent workspace
experiments/                 KCA platform experiments + not-yet-migrated comp work (e.g. tpu-getting-started)

scripts/                     Local utilities and experiment runners
tools/kca/                   KCA CLI source (kca.py + subcommand modules)
supabase/migrations/         Postgres schema migrations (forward-only, idempotent)

data/                        Local data mount — do not commit competition data
artifacts/                   Generated run artifacts — do not commit unless reviewed
runs/                        Run outputs — do not commit
```

## Quick start for a new AI session

1. Read `PROJECT_STATE.md` for current status and open decisions.
2. Read `AGENTS.md` or `CLAUDE.md` depending on your tool.
3. Read the relevant task spec under `docs/tasks/`.
4. Return a plan and wait for human approval before editing files.
5. Never read `.env`, `kaggle.json`, `secrets/`, or private keys.
6. Never submit to Kaggle, push kernels, or perform any remote write without explicit human approval.

## Current milestone: M15 next — goal-loop submit step (#77) + cross-account quota (#21)

All numbered milestones M0–M14 in `docs/milestones/README.md` are now ✓ done (M11 with T007 deferred pending live-event credentials; M12 with T007 deferred pending 3 user artefacts; M14 with T008's "≥ 2 LB scores" PASS-WITH-DEVIATION). Next prioritised work is M15 (the goal-loop submit step #77) plus the M11/M12 unblock checklists + M13.1 / M13.2 eval-case follow-ups.

M14 (goal-driven Kaggle workflow) shipped on 2026-06-10: validation matrix **21 PASS / 3 SKIP / 0 FAIL**. Delivered `kca goal {init,show,update}` + `goal.md`, `kca explore {init,run,rank,prune,propose-next}` local fan-out + holdout screening, per-competition concurrency + daily-budget gate + `cmd_push` creds pre-check, a smart kernel poller (Fibonacci QUEUED backoff / stable RUNNING / batched `kernels list`), a stuck detector with `kaggle.exploration_stuck` Approval-Inbox escalation, and migration `0011_m14_goal_loop.sql` (`goals` table + competition rule columns + `submissions.goal_id` + `experiment_runs.analysis_jsonb`) applied to cloud Supabase. The single sanctioned live series ran **2 real kernel pushes** (concurrency gate / smart poll / human approval / per-push audit all worked) but recorded **0 new LB scores** — a kernel push is not a leaderboard submission (architectural gap, issue #77) and push #2's alt-backbone kernel errored on a missing data mount; best-known LB stays M10's 0.76505. M14-T009 additionally fixed 5 cloud-schema correctness bugs the live run surfaced (run_status enum, `submissions.project_id`, `agent_jobs` schema, status casing, `refresh-rules` degradation on kaggle 2.0.1) and added the eval-suite PR gate (`eval-delta-check`, issue #63). See `docs/milestones/m14/final-review.md` and `docs/milestones/m14/handoff.md`.

M13 (evaluation, reliability, and regression suite) shipped on 2026-06-09: validation matrix **34 PASS / 4 SKIP / 0 FAIL**. Delivered 6 eval suites (tool-smoke, kaggle-replay ×3, kernel-dryrun, reasoning), 5 model routes, an aggregator producing diffable JSON + Markdown snapshots, and a nightly CI cron (`eval.yml` at 03:30 UTC). Canonical baseline snapshot at `runs/m13-eval/20260608T211005Z/`. Migration `0010_m13_eval.sql` (renumbered from 0008 — M11 took 0008 and M12 took 0009) applied to cloud Supabase. No paid LLM calls; no real Kaggle calls; cost $0.00. See `docs/milestones/m13/final-review.md` and `docs/milestones/m13/handoff.md`.

M11 (authorized CTF / lab workflow) shipped PARTIAL on 2026-06-09: T000–T006 + T008 done; T007 deferred pending human-supplied live-event credentials + approval comment. Deliverables: `supabase/migrations/0008_m11_ctf.sql` (4 ctf_* tables), `src/db/ctf.py` (6 helpers), `tools/kca/ctf.py` (12 subcommands), `data/ctf/kca-fixtures-2026/` (web-1 + crypto-1 bespoke fixtures), ADR-0016 (CTF data model) + ADR-0017 (CTF approval gates), `docs/architecture/m11-ctf-workflow.md`, 3 permission-profile extensions, 3 new approval ops, 169 tests / 0 failures. See `docs/milestones/m11/final-review.md` (23 PASS / 1 SKIP-BLOCKED / 0 FAIL) and `docs/milestones/m11/handoff.md`. Seven M11 cross-cutting follow-ups A–G filed in the handoff.

M12 (Devpost / hackathon workflow) shipped on 2026-06-09: ADR-0018 (generalized `competition_type` enum — renumbered from 0016 during PR #46 merge because M11 took 0016/0017), migration 0009 (competition_type / teams / team_memberships), Devpost adapter (`kca devpost register/fetch/info/submit`), `hackathon-experiment-loop` skill + `hackathon-runner` permission profile, `submission_checklist` tool, two new UI pages (`HackathonDeadline`, `SubmissionChecklist`), decision_api `GET /runs/<id>/submission_pack` endpoint, hand-driven local e2e run with cloud DB rows (`experiment_runs.metric_name=checklist_completion`, `metric_value=66.67`), reviewer gate for `devpost_submit` fired and pending human approval. 46 PASS / 1 DEFERRED (T007 real Devpost submit — pending 3 user artefacts; resume command in `docs/milestones/m12/final-review.md`). See `docs/milestones/m12/final-review.md` for the 48-row validation matrix and `docs/milestones/m12/handoff.md` for the M12 → M13 handoff.

M11 (authorized CTF/lab workflow) shipped PARTIAL on 2026-06-09 (T000–T006 + T008 done; T007 deferred pending human-supplied live-event credentials; see `docs/milestones/m11/final-review.md`). M12 (Devpost / hackathon workflow) shipped on 2026-06-09 (46 PASS / 1 DEFERRED — T007 real Devpost submit pending 3 user artefacts; see `docs/milestones/m12/final-review.md`). M10 (notebook-submission Kaggle regression — Petals to the Metal) shipped on 2026-05-28: validation matrix **26 PASS / 1 SKIP / 0 FAIL**. The kernel-push loop ran end-to-end correctly under the approval gates (baseline MobileNetV2 local-slice holdout **0.4310**; alt EfficientNetB0 **0.3966**, −3.4pp within the 10pp guard). **One material deviation: no public LB score was recorded** — the single approved real `kaggle kernels push` stalled QUEUED ~66 min (push #1) and the approved re-push #2 errored on a now-fixed missing `metadata.kernelspec`; per the single-push policy the human chose "accept and continue" (`submissions=03b5d080-…`, `public_score` NULL; re-push tracked by issues #34 / #35; notebook is push-ready). Issue #11 (dotenv-leak / Kaggle LB pollution) was fixed and CLOSED during M10. See `docs/milestones/m10/final-review.md` and `docs/milestones/m10/handoff.md`.

M9 (live end-to-end Kaggle regression — Spaceship Titanic) shipped on 2026-05-24: LR baseline CV **0.79144 ±0.0086**, HGB + FE CV **0.81192 ±0.00753** (+0.02048), one approved real Kaggle submission (public LB **0.78676**), two new test files (`tests/test_m9_smoke.py`, `tests/test_m9_e2e.py`). See `docs/milestones/m9/final-review.md` for the 30-check validation matrix and `docs/milestones/m9/handoff.md` for the M9 → M10 handoff.

M8.5 (pre-M9 hardening) shipped on 2026-05-23 as three PRs (#4 CI repair, #5 engineering-practice + GitHub Issues/PR/labels interface, #6 M9 planning docs); see `docs/milestones/m8_5/final-review.md` for the 26-check roll-up. M8 (product UI shell + M7 follow-ups) shipped earlier on 2026-05-23; see `docs/milestones/m8/final-review.md` for the 28-check validation matrix. The UI shell is documented in `docs/architecture/m8-ui-shell.md`; the underlying KCA CLI architecture in `docs/architecture/kca-cli-architecture.md`. The collaboration model (label routing, AI pickup rule, PR closeout) is in `docs/engineering-practice.md`. See `docs/milestones/README.md` for the full product plan (M0–M14).

## Install and configure

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | ≥ 3.11 | `uv` recommended for env management |
| Node.js | ≥ 20 | required for M8 UI shell |
| Docker | recent | for local Supabase |
| Supabase CLI | ≥ 1.200 | `brew install supabase/tap/supabase` |
| Kaggle CLI | ≥ 1.6 | `pip install kaggle` |
| `gh` CLI | ≥ 2.40 | for PR/branch operations |

### Local setup

```bash
# 1. Clone
git clone https://github.com/<your-org>/kaggle-code-agent.git
cd kaggle-code-agent

# 2. Install Python package (kca CLI)
pip install -e .
# or with uv:
uv pip install -e .

# 3. Verify kca is available
kca --help

# 4. Copy env template
cp env.example .env
# Fill in SUPABASE_DB_URL, ANTHROPIC_API_KEY, KAGGLE_USERNAME/KAGGLE_KEY

# 5. Start local Supabase
docker compose up -d        # starts supabase-db container
supabase start              # or: python -c "from tools.kca.db import ping; ping()"

# 6. Apply migrations
supabase migration up
# or directly: psql $SUPABASE_DB_URL -f supabase/migrations/<n>_*.sql

# 7. Run smoke tests (no DB required)
python -m pytest tests/ -v -m "not db"

# 8. Run full tests (DB required)
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@localhost:5432/postgres \
  python -m pytest tests/ -v
```

### Key environment variables

See `docs/tooling/env-configuration.md` for the full reference. Minimum to get started:

| Variable | Purpose |
|---|---|
| `SUPABASE_DB_URL` | Postgres DSN for local Supabase (`postgres:s3cr3t@localhost:5432/postgres`) |
| `ANTHROPIC_API_KEY` | Required for LLM calls (not needed with `--dry-run`) |
| `KAGGLE_USERNAME` / `KAGGLE_KEY` | Required for live Kaggle downloads and submissions |
| `KCA_ALLOW_REMOTE` | Set to `1` to unlock remote/prod write operations |

### Local Supabase notes

- The local Supabase DB container exposes Postgres on port 5432 (pooler) and a direct socket.
- After `docker compose down/up`, the container IP changes — use `localhost:5432` via the pooler, or re-query the container IP with `docker inspect supabase-db`.
- Migrations are forward-only and idempotent — safe to re-apply.

### Running the KCA CLI

```bash
kca skill list                        # list available agent workflow recipes
kca skill show run-milestone          # inspect a skill
kca skill run run-milestone docs/tasks/m7/M7-T001.md --dry-run
kca job list                          # list jobs
kca decision list                     # list pending approval gates
kca local probe                       # check local GPU endpoint status
```

### Claude Code project skills

- `/at-refine-issue <issue-url|number> [refinement instructions]` — refine one existing GitHub issue into an executable work order: a rewritten issue body with stable numbered, observable acceptance criteria, one standalone task comment carrying the complete task, and copyable `/goal` and plain-language launch prompts built on that comment's real permalink. Accepts a full issue URL or a number resolved against the current repository; a missing or ambiguous target is resolved before any state-changing remote call. An agent inside an already authorized goal may also invoke it from prose (`disable-model-invocation: false`), with no widening of authority. Refining is not dispatching — it never starts the work it describes. See the [skill](.claude/skills/at-refine-issue/SKILL.md), its [issue-body](.claude/skills/at-refine-issue/references/issue-body.md) and [task-comment](.claude/skills/at-refine-issue/references/task-comment.md) references, and its [validation](docs/testing/at-refine-issue.md). In Codex, explicitly ask it to read `.claude/skills/at-refine-issue/SKILL.md` and pass the same arguments; this Claude project directory does not imply automatic Codex skill discovery.

- `/at-review-pr [pr=<n>] [rounds] [reviewer] [writer]` — bounded review/fix rounds on the PR named by `pr=<n>`, otherwise the PR in context, otherwise the current branch's unique open PR. `pr=<n>` is optional and recognized only as the first token, so the three positional arguments keep their order after it; `rounds` defaults to 10 and any supplied value must be a positive integer; providers default to `codex` / `claude` and either position accepts either provider. Uses independent sessions, evidence-linked dispositions, and a full review of the final head before approval. An agent may also invoke it from a natural-language goal (`disable-model-invocation: false`), using the round budget stated there. See the [skill](.claude/skills/at-review-pr/SKILL.md) and its [validation](docs/testing/at-review-pr.md). In Codex, explicitly ask it to read that file and supply the same arguments; this Claude project directory does not imply automatic Codex skill discovery.

- `/save-log <name|id>` — export a stopped or completed Claude Code background session transcript to `logs/<name>.md` via `claude-code-log`. See `.claude/skills/save-log/SKILL.md`.

### Cloud deployment (placeholder — not yet implemented)

The platform is designed to run locally first. Cloud deployment will be added in a future milestone. Planned targets:

- **AWS**: ECS/Fargate for worker containers, RDS or Supabase hosted for DB, S3 for artifact storage, SQS/EventBridge for job queue.
- **GCP**: Cloud Run for workers, Cloud SQL or Supabase hosted for DB, GCS for artifacts, Cloud Tasks for job queue.

When cloud deployment is ready, a `docs/deployment/` directory will contain per-provider runbooks. Environment variable `KCA_DEPLOY_TARGET=local|aws|gcp` will select the active runtime. All remote write operations will still require `KCA_ALLOW_REMOTE=1` and human approval gates.

## Safety rules summary

- Secrets never enter repo, prompts, logs, or screenshots.
- Kaggle submissions, kernel pushes, and dataset uploads require explicit human approval.
- CTF/lab work must be local/sandboxed or explicitly authorized.
- Every AI task that modifies code should use a branch or worktree so `main` remains stable.
- Do not allow multiple AI sessions to edit the same branch or files simultaneously.
