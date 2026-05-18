# M2-T002: local Supabase development workflow

## Milestone
M2: Supabase / control-plane foundation.

## Goal
Make `supabase start` the canonical local control plane for kca development.
A new developer should be able to bring up Postgres + Storage + Studio with
one command, apply migrations 0001 and 0002, and run smoke tests against it.

## Read first
1. `supabase/migrations/0001_init.sql`
2. `supabase/migrations/0002_kca_run_alignment.sql` (from T001)
3. Supabase CLI docs (`supabase --help`, `supabase start`, `supabase db reset`)
4. ADR-002 (Supabase as control plane)

## Required deliverables
- `supabase/config.toml` configured for local-first (no remote project linked).
- `Makefile` targets (or `scripts/`): `supabase-up`, `supabase-down`, `supabase-reset`, `supabase-psql`.
- `docs/tooling/local-supabase.md` with the full setup walkthrough:
  - Prereqs (Docker, supabase CLI version pin).
  - `supabase init` (if needed), `supabase start`, apply migrations.
  - How to access Studio (default `http://localhost:54323`).
  - How to get the local connection string for kca (`SUPABASE_URL=...`, `SUPABASE_DB_URL=postgres://...`).
  - How to reset cleanly.
- `.gitignore` entries for any local supabase state directories.

## Design constraints
- Do not commit credentials. Local dev uses Supabase CLI's auto-generated dev keys; document where to find them.
- Do not configure a remote Supabase project in this task — M3+ work.
- Keep the Makefile portable (POSIX-ish; macOS + Linux). No bash-only constructs unless wrapped.

## Non-goals
- No real-time / Edge Functions.
- No Storage buckets yet (M3).
- No auth schema customization yet.

## Acceptance criteria
- `make supabase-up` starts a fresh local stack (or prints the manual command if `make` is not used).
- After bringing up the stack, migrations 0001 and 0002 apply cleanly with no errors.
- `make supabase-psql` (or documented equivalent) opens a psql shell against the local DB.
- `docs/tooling/local-supabase.md` is followable by someone who has never used Supabase before.

## Suggested checks
```bash
supabase --version
make supabase-up         # or: supabase start
supabase db reset --debug  # applies migrations cleanly
psql "$SUPABASE_DB_URL" -c "select count(*) from projects;"
```

## Stop condition
Stop after 40 turns if the Supabase CLI has cross-platform issues — record
the failure mode and propose either a pinned version or a docker-compose
fallback in `docs/tooling/local-supabase.md`.
