# Local Supabase development setup

This is the canonical local control plane for `tt_pangu`. The Supabase CLI
boots a full stack — Postgres + PostgREST + Storage + Studio + Auth + Realtime —
in Docker. You only need Postgres + Studio for M2 work, but it's all bundled.

## Prerequisites

- **Docker** running on the local machine.
- **Supabase CLI ≥ 2.0**. Verified with `supabase 2.98.x`.
- **psql** (Postgres client) for ad-hoc queries.
- **Python deps** for the kca DB layer (`tools/kca/db.py`):

  ```bash
  pip install 'psycopg[binary]>=3.2'
  ```

  `psycopg[binary]` ships libpq so no system libpq install is required.

Quick install (Arch Linux example, macOS / Linux variants in
[Supabase docs](https://supabase.com/docs/guides/local-development/cli/getting-started)):

```bash
# Arch
yay -S supabase-bin
# macOS
brew install supabase/tap/supabase
```

## First-time setup

The repo is already initialized — `supabase/config.toml` lives at the project
root, and `supabase/migrations/0001_init.sql` + `0002_kca_run_alignment.sql`
are committed. No `supabase init` needed.

```bash
cd tt_pangu/
make supabase-up      # equivalent to: supabase start
```

First run takes 1–3 minutes because Docker pulls the Supabase images
(~600 MB total). Subsequent runs are seconds.

When `supabase start` finishes, it prints the local URLs and dev keys.
Re-print them anytime with:

```bash
make supabase-status   # equivalent to: supabase status
```

Defaults (from `supabase/config.toml`):

| Service | URL | Port |
|---|---|---|
| API (PostgREST) | http://127.0.0.1:54321 | 54321 |
| Database | postgres://postgres:postgres@127.0.0.1:54322/postgres | 54322 |
| Studio (admin UI) | http://127.0.0.1:54323 | 54323 |
| Inbucket (email) | http://127.0.0.1:54324 | 54324 |

The DB credentials above are the **CLI's hardcoded dev defaults**. They are
not secrets and never touch a remote Supabase project — they only work
against the local Docker stack.

## Day-to-day commands

```bash
# Bring up the stack (or no-op if already up)
make supabase-up

# Open the admin UI in your browser
open http://127.0.0.1:54323

# Open a psql shell
make supabase-psql

# Wipe the local DB and re-apply migrations 0001, 0002, ...
make supabase-reset    # equivalent to: supabase db reset

# Tear down (containers stop; volumes preserved)
make supabase-down

# Full clean (containers + volumes)
supabase stop --no-backup
```

## Verifying the schema is healthy

```bash
psql "postgres://postgres:postgres@127.0.0.1:54322/postgres" -c "
  select tablename from pg_tables where schemaname='public' order by tablename;
"
```

Expected tables after applying both migrations:

```
agent_events
agent_jobs
agent_sessions
artifacts
competitions
ctf_scopes
experiment_run_metrics       -- added by 0002
experiment_runs
experiments
human_decisions
messages
projects
research_items
submissions
```

Verify the bootstrap project row from migration 0002:

```bash
psql "postgres://postgres:postgres@127.0.0.1:54322/postgres" -c "
  select id, name, kind from projects where name='local-default';
"
```

Should return one row with `id = 00000000-0000-0000-0000-000000000001`.

## Where things live

- `supabase/config.toml` — local stack ports, schema config, auth providers. Committed.
- `supabase/migrations/*.sql` — ordered, forward-only migrations. Committed.
- `supabase/.gitignore` — ignores `.temp/`, `.branches/`, `.env.local`. Committed.
- `supabase/.temp/` — CLI scratch state. Ignored.

## Adding a new migration

```bash
supabase migration new my_change_name
# edits supabase/migrations/<timestamp>_my_change_name.sql
make supabase-reset   # wipes + re-applies, including the new file
```

Migrations are applied in lexicographic filename order. Keep them
forward-only; don't drop columns or tables in M2.

## Connecting from kca / Python

The Python DB layer (M2-T003) reads `SUPABASE_DB_URL`:

```bash
export SUPABASE_DB_URL="postgres://postgres:postgres@127.0.0.1:54322/postgres"
export KCA_DB_TARGET=local
python tools/kca/kca.py run init --competition titanic --hypothesis "b" --json
```

Or via Make:

```bash
make test-db-smoke
make kca-runs
```

## Troubleshooting

### `supabase start` fails: port already in use

Another Postgres / Supabase / Docker container is on 54321 / 54322 / 54323.
Either stop the other one (`docker ps` then `docker stop <id>`) or edit
`supabase/config.toml` to change ports (don't commit the port change unless
the team agrees).

### `supabase: command not found`

Install the CLI (see Prerequisites). Don't add `npx supabase` indirections —
this project standardizes on a system-installed CLI.

### Migrations fail with `relation already exists`

You ran `supabase start` on a stack that previously applied migrations and
already has the tables. Use `make supabase-reset` to wipe and re-apply.

### Docker permission denied

Add your user to the `docker` group (`sudo usermod -aG docker $USER`) or run
Docker rootless. Don't use `sudo make supabase-up` — that puts container
files under root ownership.

### Resetting from a clean slate

```bash
supabase stop --no-backup   # also drops volumes
make supabase-up
```

## What's not in scope for M2

- Remote Supabase project linking (`supabase link`). M3+.
- Custom auth providers / RLS policies. M3+.
- Edge Functions. M5+.
- Production secrets management. M3+.
