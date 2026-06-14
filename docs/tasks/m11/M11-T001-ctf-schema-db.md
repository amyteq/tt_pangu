# M11-T001: CTF schema (migration 0008) + DB helpers

## Milestone
M11: authorized CTF / lab workflow. **`arch:` tagged** — Discovery / Debate
Gate evidence (T000) is the source of truth for the schema shape.

## Goal
Author `supabase/migrations/0008_m11_ctf.sql` adding `ctf_events`,
`ctf_challenges`, and `ctf_attempts` tables; confirm the existing
`ctf_scopes` table (migration 0001) is reachable; add DB helpers in
`src/db/ctf.py`; record the design in `docs/adr/0016-ctf-data-model.md`.

## Read first

1. `PROJECT_STATE.md`
2. `docs/milestones/README.md` §M11
3. M11-T000 closeout + `docs/evidence/m11/discovery/legacy-archaeologist.md`
   (load-bearing for schema dimensions)
4. `docs/evidence/m11/discovery/design-red-team.md` (alternatives + dropped
   capability list)
5. `supabase/migrations/0001_init.sql` — `ctf_scopes` table shape
6. `supabase/migrations/0004_m4_competition_repo.sql` — latest extension
   precedent
7. `supabase/migrations/0007_m8_tool_audit.sql` — most recent migration
8. `src/db/__init__.py`, `src/db/research.py` — helper-function shape
9. `docs/adr/0005-job-taxonomy.md` — `project_kind` enum
10. `docs/architecture/m11-ctf-workflow.md` (if drafted in T000 closeout)

## Scope

1. **Author `supabase/migrations/0008_m11_ctf.sql`** with three tables:

   ```sql
   create table ctf_events (
     id uuid primary key default gen_random_uuid(),
     project_id uuid not null references projects(id) on delete cascade,
     slug text not null unique,
     name text not null,
     ctftime_event_id integer,
     event_url text,
     start_at timestamptz,
     end_at timestamptz,
     scoring text default 'jeopardy',
     credentials_ref text,  -- path hint, e.g. '~/.ctf/<slug>.json'; never the value
     notes text,
     created_at timestamptz not null default now()
   );

   create table ctf_challenges (
     id uuid primary key default gen_random_uuid(),
     event_id uuid not null references ctf_events(id) on delete cascade,
     scope_id uuid references ctf_scopes(id) on delete set null,
     slug text not null,
     name text not null,
     category text not null check (category in ('web','crypto','rev','pwn','forensics','osint','misc')),
     points integer,
     description text,
     expected_flag_format text,
     attachments_path text,
     remote_endpoint text,
     created_at timestamptz not null default now(),
     unique (event_id, slug)
   );

   create table ctf_attempts (
     id uuid primary key default gen_random_uuid(),
     challenge_id uuid not null references ctf_challenges(id) on delete cascade,
     run_id uuid references experiment_runs(id) on delete set null,
     accepted boolean,
     http_status integer,
     flag_length integer,  -- NEVER the flag value
     submitted_at timestamptz not null default now(),
     response_excerpt text  -- 256-char cap, redact any string that looks like a flag
   );
   ```
   RLS enabled on all three; no policies yet (same posture as `ctf_scopes`
   in migration 0001).

2. **Apply against the local container only.**
   `dangerouslyDisableSandbox=true`; `psql $SUPABASE_DB_URL -f
   supabase/migrations/0008_m11_ctf.sql`. NEVER apply to a remote /
   production DSN.

3. **Add `src/db/ctf.py`** with helpers (functions only — no
   side-effects at import):
   - `register_event(project_id, slug, name, **kwargs) -> uuid`
   - `add_challenge(event_id, slug, name, category, **kwargs) -> uuid`
   - `set_scope_for_challenge(challenge_id, scope_id) -> None`
   - `record_attempt(challenge_id, accepted, http_status, flag_length, response_excerpt, run_id=None) -> uuid`
   - `list_events(project_id=None) -> list[dict]`
   - `get_challenge(event_slug, challenge_slug) -> dict | None`
   - `list_attempts(challenge_id, limit=50) -> list[dict]`
   All helpers MUST refuse to log `flag_length` together with any
   challenge-specific identifier that would let an observer reconstruct
   the flag from `response_excerpt` + length.

4. **Write `docs/adr/0016-ctf-data-model.md`** documenting:
   - Multi-event identity model (`(project_id, slug)` unique on events,
     `(event_id, slug)` unique on challenges).
   - Why `credentials_ref` is a path hint (string) not the value.
   - Why `ctf_attempts.flag_length` is recorded but `flag_value` is not.
   - Retention policy for failed attempts (default: keep indefinitely;
     attempt-level redaction is in the `response_excerpt` capture).
   - Cross-link to T000's `design-red-team.md` for dropped capabilities.

5. **Smoke tests** under `tests/test_m11_db.py` (DB-gated like
   `tests/test_m9_smoke.py`): register an event, add a challenge,
   record an attempt, list events / challenges / attempts; assert
   constraints fire (unique violation, FK cascade).

## Non-goals

- Do not modify `.kca/permissions/`, `src/worker/`, `tools/kca/`, or
  `.claude/settings.json` in this Loop Prompt. Those belong to T002+.
- Do not author CLI subcommands. T003 owns `tools/kca/ctf.py`.
- Do not insert any real challenge / event rows. T004 owns fixtures.
- Do not echo any flag value, credential value, or `~/.ctf/*` content
  in DB rows, logs, or the closeout.

## Acceptance criteria

- `supabase/migrations/0008_m11_ctf.sql` exists and applies cleanly to
  the local container; `\dt ctf_*` shows four tables (`ctf_events`,
  `ctf_challenges`, `ctf_attempts`, `ctf_scopes` from 0001).
- `python -c "from src.db.ctf import register_event, add_challenge,
  record_attempt; print('ok')"` — exits 0.
- `tests/test_m11_db.py` passes against the local container under
  `SUPABASE_DB_URL`; SKIPs cleanly without it (mirror M9 smoke posture).
- `docs/adr/0016-ctf-data-model.md` exists with the five sections
  named in scope step 4.
- No real flag value, credential value, or `~/.ctf/*` content appears
  in any committed file or row.

## Permissions

- Local file writes under `supabase/migrations/`, `src/db/`,
  `tests/`, `docs/adr/`.
- `psql` against the local DSN under `dangerouslyDisableSandbox=true`.
- NEVER apply migrations to a remote/production DSN.

## Closeout format

```
M11-T001 closeout
  Migration: supabase/migrations/0008_m11_ctf.sql applied to local container
  Tables present: ctf_events, ctf_challenges, ctf_attempts, ctf_scopes (4/4)
  src/db/ctf.py helpers: <list>
  ADR-0016: docs/adr/0016-ctf-data-model.md present (sections: 5/5)
  tests/test_m11_db.py: <n> passed, <m> skipped (DB gate)
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T002 ready to start
```

## Related issues

- M11 proposal issue (TBD). M11-T001 closes the "schema + DB helpers"
  bullet.

## Stop condition

Stop after 80 turns. If `0008_m11_ctf.sql` fails to apply due to a
schema conflict with an unanticipated existing column / index, halt
and ask. If the helpers cannot be authored without violating the
"never log flag value" invariant (e.g. an FK constraint forces a join
that exposes flag-derived info), halt and propose an ADR amendment.
