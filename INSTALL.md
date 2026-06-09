# Installation and Configuration

This guide covers running the KCA platform locally. Cloud deployment instructions will be added in a future milestone.

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.11 | [python.org](https://www.python.org/) or `uv` |
| `uv` | latest | `curl -Ls https://astral.sh/uv/install.sh \| sh` |
| Docker | recent | [docker.com](https://www.docker.com/) |
| Supabase CLI | ≥ 1.200 | `brew install supabase/tap/supabase` or [supabase.com/docs/guides/cli](https://supabase.com/docs/guides/cli) |
| Kaggle CLI | ≥ 1.6 | `pip install kaggle` |
| `gh` CLI | ≥ 2.40 | `brew install gh` |
| Node.js | ≥ 20 | required for M8+ UI shell only |

## Clone and install

```bash
git clone https://github.com/<your-org>/kaggle-code-agent.git
cd kaggle-code-agent

# Install the kca Python package in editable mode
pip install -e .
# or with uv:
uv pip install -e .

# Verify
kca --help
```

## Configure environment

```bash
cp env.example .env
```

Open `.env` and fill in the required values:

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_DB_URL` | yes | Postgres DSN — see §Local Supabase below |
| `ANTHROPIC_API_KEY` | yes (except `--dry-run`) | Claude API key |
| `KAGGLE_USERNAME` | for Kaggle ops | Your Kaggle username |
| `KAGGLE_KEY` | for Kaggle ops | Your Kaggle API key |
| `KCA_DB_TARGET` | default `local` | `local` or `remote` |
| `KCA_ALLOW_REMOTE` | default unset | Set to `1` to allow remote/prod writes |

Full variable reference: `docs/tooling/env-configuration.md`.

## Local Supabase

KCA uses a local Supabase stack (Postgres + Auth + Storage) via Docker.

```bash
# Start the containers
docker compose up -d

# Apply all migrations
supabase migration up

# Verify
kca run list   # should return empty list without errors
```

The default local DSN is:
```
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@localhost:5432/postgres
```

> **Note:** After `docker compose down && docker compose up`, the container's internal IP changes. Use `localhost:5432` (pooler) for DSN, or re-query the container IP:
> ```bash
> docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
> ```

## Run tests

```bash
# No DB (CI-safe)
python -m pytest tests/ -v -m "not db"

# With local DB
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@localhost:5432/postgres \
  python -m pytest tests/ -v

# Lint
ruff check .
ruff format --check .
```

### Enforce ruff before every push (recommended)

CI runs `ruff check .` and `ruff format --check .`; enable the repo's pre-push
hook so format/lint drift is caught locally before a push or PR (once per clone):

```bash
git config core.hooksPath .githooks
```

Bypass for a deliberate WIP push with `SKIP_RUFF_GATE=1 git push …` or
`git push --no-verify`. (Claude Code sessions are additionally gated by
`.claude/hooks/format_gate.py`.)

## Worklogs dump (daily, automated)

Claude session transcripts for this project are exported to Markdown and merged
to `main` on a daily schedule by a **systemd user timer**. Setup and operation:
[`docs/tooling/worklogs-systemd-timer.md`](docs/tooling/worklogs-systemd-timer.md).

## KCA CLI quick reference

```bash
kca skill list                                   # list available workflow recipes
kca skill show run-milestone                     # inspect skill metadata
kca skill run run-milestone docs/tasks/M001.md --dry-run

kca job list                                     # list jobs
kca job run <job-id>
kca job logs <job-id>

kca decision list                                # pending approval gates
kca decision approve <decision-id>
kca decision reject <decision-id>

kca local probe                                  # check local GPU endpoints
kca local list

kca review list                                  # reviewer verdicts
kca kaggle download <competition>                # download data
kca kaggle verify <competition>                  # sha256 check
# kca kaggle submit <run-id>                     # requires human approval gate
```

## Local GPU endpoints (optional)

If you have GPU hosts running vLLM or Ollama, configure them for local model routing:

```bash
# In .env:
KCA_LOCAL_ENDPOINT_0_URL=http://192.168.18.66:8000/v1
KCA_LOCAL_ENDPOINT_0_NAME=snorlax-vllm
KCA_LOCAL_ENDPOINT_0_MODEL=rtx4090
KCA_LOCAL_ENDPOINT_0_PRIORITY=10

KCA_LOCAL_FALLBACK_MODEL=claude-haiku-4-5
```

```bash
kca local probe --json   # verify endpoints are reachable
```

## Claude Code integration

KCA ships `.kca/skills/` for use with Claude Code's `/` skill invocation. After installation, Claude Code sessions in this repo can call:

```
/run-milestone docs/tasks/M7-T001.md
/triage-log
/prepare-submission
```

Permissions for unattended runs are configured in `.claude/settings.json`. For long `goal`-style tasks:

```bash
claude --permission-mode dontAsk
```

See `docs/meeting-notes/2026-05-21-r1.md` §6–9 for the full permission model.

---

## Cloud deployment (not yet implemented)

KCA is local-first for MVP. Cloud deployment will be documented under `docs/deployment/` in a future milestone. Planned targets:

### AWS

```text
Workers:     ECS / Fargate (Python containers)
Database:    RDS Postgres or Supabase Cloud
Artifacts:   S3
Job queue:   SQS or EventBridge Pipes
Secrets:     AWS Secrets Manager
```

### GCP

```text
Workers:     Cloud Run (Python containers)
Database:    Cloud SQL Postgres or Supabase Cloud
Artifacts:   GCS
Job queue:   Cloud Tasks
Secrets:     Secret Manager
```

When cloud deployment is implemented:

- Set `KCA_DEPLOY_TARGET=aws` or `KCA_DEPLOY_TARGET=gcp`.
- All remote write operations still require `KCA_ALLOW_REMOTE=1` and pass through the human approval gate.
- Schema migrations are applied via `supabase db push` (remote), which is an `ask`-level operation.
