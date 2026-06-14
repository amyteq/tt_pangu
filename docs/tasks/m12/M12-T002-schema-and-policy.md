# M12-T002: Migration 0009 (competition_type / teams / deadline) + policy resolver refactor

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Land the schema and code changes ADR-0018 specified:

1. `supabase/migrations/0009_m12_competition_type_teams.sql` adds:
   - `competition_type_enum` postgres enum;
   - `competitions.competition_type` (default `'kaggle'`);
   - `competitions.deadline timestamptz NULL`;
   - `competitions.submission_format jsonb NULL`;
   - `teams` and `team_memberships` tables.
2. `src/worker/_types.py::JobPolicy` and
   `tools/kca/agent/permission_policy.py` route gate resolution on
   `competition_type`, falling back to the existing default profile
   when no type-specific profile is found.
3. M9 / M10 baseline rows still resolve their policy correctly
   (regression). Migration is idempotent + backwards-compatible.

## Tag

Routine. (T001's `arch:` gate already covered this design.)

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M12
3. `docs/milestones/m12/loop-prompts.md` Loop Prompt 2
4. `docs/adr/0018-generalized-competition-type.md` (T001 output)
5. `docs/adr/0006-configurable-approval-gates.md`
6. `supabase/migrations/0004_m4_competition_repo.sql` — adds the
   existing `competitions` columns; mirror that style
7. `supabase/migrations/0006_m6_reviews_spans.sql`,
   `supabase/migrations/0007_m8_agent_tool_audit.sql` — recent migration style
8. `src/worker/_types.py::JobPolicy`
9. `tools/kca/agent/permission_policy.py`
10. `src/worker/tools.py` — gate lookup path
11. `tests/test_m4_smoke.py`, `tests/test_m7_smoke.py` — DB-gated test pattern
12. `src/db/competition.py` (if present) — competition CRUD helpers

## Scope

1. Author `supabase/migrations/0009_m12_competition_type_teams.sql`.
   The file MUST:
   - Use `CREATE TYPE IF NOT EXISTS competition_type_enum AS ENUM
     ('kaggle','devpost','hackathon_devpost','ctf','generic');` (or the
     guarded `DO $$ ... $$` equivalent if `IF NOT EXISTS` is not
     supported for `CREATE TYPE` on the local Postgres version).
   - `ALTER TABLE competitions ADD COLUMN IF NOT EXISTS competition_type
     competition_type_enum NOT NULL DEFAULT 'kaggle';`
   - `ALTER TABLE competitions ADD COLUMN IF NOT EXISTS deadline
     timestamptz NULL;`
   - `ALTER TABLE competitions ADD COLUMN IF NOT EXISTS submission_format
     jsonb NULL;`
   - `CREATE TABLE IF NOT EXISTS teams (id uuid PRIMARY KEY DEFAULT
     gen_random_uuid(), name text NOT NULL, owner_user_id uuid NOT NULL,
     created_at timestamptz NOT NULL DEFAULT now());`
   - `CREATE TABLE IF NOT EXISTS team_memberships (team_id uuid NOT NULL
     REFERENCES teams(id), user_id uuid NOT NULL, role text NOT NULL
     DEFAULT 'member', joined_at timestamptz NOT NULL DEFAULT now(),
     PRIMARY KEY (team_id, user_id));`
   - Be idempotent (re-runnable without error).
2. Apply the migration locally (`psql $SUPABASE_DB_URL -f
   supabase/migrations/0008_*.sql`).
3. Refactor `JobPolicy`:
   - Add a `competition_type` field (defaults to `'kaggle'` for backwards
     compatibility).
   - Update the resolver in `permission_policy.py` to route on
     `competition_type` first, then fall back to the default profile.
4. Add minimal DB helpers (in `src/db/teams.py` or extend `src/db/competition.py`):
   - `create_team(name, owner_user_id) -> team_id`
   - `add_team_member(team_id, user_id, role='member') -> None`
   - `get_team_members(team_id) -> list[dict]`
   No delete helpers in M12 (deferred).
5. Verify M9 / M10 baseline rows still resolve their policy correctly:
   - Query: `SELECT slug, competition_type FROM competitions;` —
     existing rows show `'kaggle'`.
   - Run `kca run list --json` for an M9 baseline run; confirm the
     gate resolution result is unchanged.
6. Add 2–3 targeted unit tests under `tests/test_m12_policy.py` (no
   DB; resolver-only) covering: kaggle row → existing profile;
   devpost row → hackathon-runner profile (the profile itself ships
   in T004; this test stubs the profile registry); unknown
   competition_type → falls back to default.

## Non-goals

- Do NOT write `.kca/permissions/hackathon-runner.yaml`. That's T004.
- Do NOT write `tools/kca/devpost.py`. That's T003.
- Do NOT add UI changes. That's T005.
- Do NOT add `submission_url` / `submission_id` columns to
  `submissions`. Those already exist from earlier milestones; M12-T007
  uses them as-is.
- Do NOT add a `competitions.platform` column. The `competition_type`
  enum replaces any prior need for it.
- Do NOT add team-role logic beyond `role text DEFAULT 'member'`.
  Owner is on the team row; role enforcement is a follow-up.

## Acceptance criteria

- `supabase/migrations/0009_m12_competition_type_teams.sql` exists,
  is idempotent, and has been applied locally.
- `psql $SUPABASE_DB_URL -c "\d competitions"` shows the three new
  columns; `\d teams` and `\d team_memberships` exist.
- `psql $SUPABASE_DB_URL -c "SELECT DISTINCT competition_type FROM
  competitions;"` returns rows containing `kaggle` only (pre-M12
  rows backfilled correctly).
- `src/worker/_types.py::JobPolicy` carries a `competition_type` field
  with default `'kaggle'`.
- `tools/kca/agent/permission_policy.py` routes on `competition_type`;
  unknown values fall back to default; existing tests still pass.
- `tests/test_m12_policy.py` passes (no DB required); existing
  `tests/test_m4_smoke.py`, `tests/test_m7_smoke.py`, `tests/test_m9_smoke.py`,
  `tests/test_m9_e2e.py` all still pass.
- `ruff check .` clean.
- `kca run list --json` for an M9 baseline run still resolves the
  Kaggle gate path (no behavioural regression).

## Permissions

- File writes to: `supabase/migrations/0008_*.sql`, `src/worker/_types.py`,
  `tools/kca/agent/permission_policy.py`, `src/db/teams.py` (new) or
  `src/db/competition.py` (extend), `tests/test_m12_policy.py` (new).
- DB writes via `psql` to apply the migration; needs
  `dangerouslyDisableSandbox=true` per memory `reference_supabase_db.md`.
- No `kca` write subcommands beyond what the local migration apply
  requires. No Devpost / Kaggle network calls.
- `git commit` / `git push` deferred to T009 closeout.

## Closeout format

```
M12-T002 closeout
  Migration: supabase/migrations/0009_m12_competition_type_teams.sql
  Applied locally: YES
  competitions columns: competition_type | deadline | submission_format
  teams + team_memberships: present
  JobPolicy.competition_type: present (default='kaggle')
  Resolver routes on competition_type: YES
  M9 / M10 baseline rows: competition_type='kaggle' (no behavioural regression)
  Tests passing: tests/test_m12_policy.py + existing suite
  Acceptance: PASS | FAIL — link to closing issue
  Risks / blockers: ...
  Next: M12-T003 (devpost adapter, READ_ONLY)
```

## Related issues

- ADR-0018 (T001 output) — referenced for every design decision.
- Closing issue for M12 — gets a comment linking the migration file
  and confirming the M9 / M10 regression check.

## Stop condition

Stop after 80 turns. If migration apply fails on the local DB, halt and
diagnose — do NOT drop / recreate `competitions`. If any M9 / M10
baseline row's policy resolution changes, halt and ask — the
generalization must be backwards-compatible.
