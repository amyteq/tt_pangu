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
- `docs/milestones.md` — product plan from M0 through M12

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
  milestones.md              Product plan M0–M12
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

## Current milestone: M9 — live Kaggle regression test

Status: planned. Scope: drive the M8 surface end-to-end against a real Kaggle competition (Spaceship Titanic) under the approval gates — baseline training, CV scoring, submission preparation, human-approved submit, leaderboard ingest.

M8 (product UI shell + M7 follow-ups) shipped on 2026-05-23; see `docs/m8-final-review.md` for the 28-check validation matrix and M9 follow-ups. The UI shell is documented in `docs/architecture/m8-ui-shell.md`; the underlying KCA CLI architecture in `docs/architecture/kca-cli-architecture.md`. See `docs/milestones.md` for the full product plan (M0–M12).

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
kca skill run run-milestone docs/tasks/M7-T001.md --dry-run
kca job list                          # list jobs
kca decision list                     # list pending approval gates
kca local probe                       # check local GPU endpoint status
```

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
