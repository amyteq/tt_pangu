# Environment Configuration

All runtime secrets and deployment-specific settings live in a `.env` file
at the repo root.  **Never commit `.env`** — use `env.example` as the template.

## Quick start

```bash
cp env.example .env
# Edit .env with your real values
```

`tools/kca/db.py` and `scripts/run_job.py` both load `.env` automatically via
`python-dotenv` if it is installed:

```bash
pip install python-dotenv   # one-time; already pulled in by litellm
```

If `python-dotenv` is absent, set env vars in your shell or CI environment manually.

---

## Variable reference

### Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `SUPABASE_DB_URL` | **yes** (or discrete vars) | — | libpq DSN string. Preferred over the discrete vars below. |
| `KCA_DB_TARGET` | no | `local` | `local` = LOCAL\_WRITE classification; `remote` = REMOTE\_WRITE gate. |
| `KCA_ALLOW_REMOTE` | conditional | — | Set to `1` to allow remote/submission operations when `KCA_DB_TARGET=remote`. |
| `SUPABASE_DB_HOST` | fallback | — | Only used when `SUPABASE_DB_URL` is unset. |
| `SUPABASE_DB_PORT` | fallback | `54322` | Direct Postgres port (Supabase default). |
| `SUPABASE_DB_USER` | fallback | `postgres` | |
| `SUPABASE_DB_PASSWORD` | fallback | `postgres` | |
| `SUPABASE_DB` | fallback | `postgres` | Database name. |

#### Connection string examples

```bash
# Standard local Supabase (supabase start, port 54322 mapped to host)
SUPABASE_DB_URL=postgresql://postgres:postgres@localhost:54322/postgres

# Local Supabase when port 54322 is not host-mapped (e.g. this repo's setup):
# Get the container IP first:
#   docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres?sslmode=disable

# Hosted / production Supabase
SUPABASE_DB_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
```

> **Note on Supavisor (port 5432 / 6543):** The Supabase pooler requires a
> tenant header when connecting via `localhost:5432`.  Use the direct container
> IP on port 5432 (bypassing Supavisor) or the standard port 54322 if it is
> host-mapped.  See [local-supabase.md](local-supabase.md) for setup details.

---

### LLM providers

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | For `model=claude-*` | Not needed for `--dry-run`. |
| `OPENAI_API_KEY` | For `model=gpt-4o` / `o3` | |
| `GEMINI_API_KEY` | For `model=gemini/*` | |
| `GROQ_API_KEY` | For `model=groq/*` | |

See [ADR-0004](../adr/0004-litellm-provider-layer.md) for the full model string reference.

---

### Kaggle

| Variable | Required | Description |
|---|---|---|
| `KAGGLE_USERNAME` | For live submissions | Set directly; do not use `kaggle.json`. |
| `KAGGLE_KEY` | For live submissions | |

---

### Worker defaults

These can all be overridden per-job via `JobPolicy` or `scripts/run_job.py` CLI flags.

| Variable | Default | CLI flag |
|---|---|---|
| `KCA_DEFAULT_MAX_TURNS` | `30` | `--max-turns` |
| `KCA_DEFAULT_MAX_COST_USD` | `5.0` | `--max-cost-usd` |
| `KCA_DEFAULT_MODEL` | `claude-sonnet-4-6` | `--model` |

---

## Deployment notes

### Local development
Use `supabase start` (see [local-supabase.md](local-supabase.md)).  Copy
`env.example` → `.env`, fill in `SUPABASE_DB_URL` and optionally `ANTHROPIC_API_KEY`.

### CI / GitHub Actions
Set secrets in the repository settings.  The workflow injects them as env vars;
no `.env` file needed.

### Standalone server deployment
Provide `.env` (or system env vars) on the target machine.  Set
`KCA_DB_TARGET=remote` and `SUPABASE_DB_URL` to the hosted Supabase DSN.
Set `KCA_ALLOW_REMOTE=1` only on machines that are permitted to submit to Kaggle
or push to external services.
