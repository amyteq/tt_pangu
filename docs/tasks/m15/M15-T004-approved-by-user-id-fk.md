# M15-T004: `approved_by_user_id` FK on `human_decisions` (issue #60 — ADR-0018 F2)

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Add a structured `approved_by_user_id` column on `human_decisions` (migration
0012) so approval audit rows carry the actual approver identity rather than only
free-text `rationale`. `kca decisions approve` populates it; the permission
policy can read it to enforce owner-only on team-scoped ops. The FK target
(`auth.users`) is deferred until Supabase auth lands — column allows NULL and
the gap is documented.

Independent of T001/T002 — runs in any order within the ADR-0018 hardening group.

## Read first
1. Issue #60 (acceptance criteria — pin to the issue body).
2. `docs/adr/0018-generalized-competition-type.md` §"Team-scoped operation rules".
3. `supabase/migrations/0001_init.sql:157` (`human_decisions` table; note
   `rationale` is the free-text column, not `notes`).
4. Most-recent migration `supabase/migrations/0011_m14_goal_loop.sql` (0012 is
   the next free number).
5. `tools/kca/decisions.py` — `cmd_approve` (~63).
6. `tools/kca/agent/permission_policy.py` (owner-only enforcement consumer).

## Scope
1. **Migration 0012** (`supabase/migrations/0012_m15_*.sql`) adds
   `human_decisions.approved_by_user_id uuid NULL`. FK to a stable user identity
   table (`auth.users`) is deferred until Supabase auth lands — allow NULL now,
   document the deferred FK in the migration comment + ADR note.
2. `kca decisions approve` (`cmd_approve`) populates `approved_by_user_id` from
   the calling identity (resolved per the current Decision API token; multi-user
   JWT wins if/when it lands).
3. `tools/kca/agent/permission_policy.py` can read the column to enforce
   owner-only on team-scoped ops (NULL-tolerant path: pre-existing rows stay
   NULL and resolve as today).

## Non-goals
- No Supabase auth implementation — only the NULL column + populate + read path.
- No change to `rationale` (the new column is in addition, not a replacement).
- No team-role enforcement rollout (that's the future milestone this unblocks).

## Acceptance criteria
_Pinned to issue #60:_
- New migration (0012) adds `human_decisions.approved_by_user_id uuid NULL` with
  FK to a stable user identity table (likely `auth.users` once Supabase auth
  lands; interim: NULL allowed, gap documented).
- `kca decisions approve` populates the column from the calling user.
- `tools/kca/agent/permission_policy.py` can use the column to enforce
  owner-only on team-scoped ops.
- Backwards-compatible: existing M9/M10/M11/M12 rows leave the column NULL.
- Tests cover both the populate path and the NULL-tolerant resolver path.
- `ruff check .` / `ruff format --check .` clean; migration applies cleanly
  against cloud Supabase.

## Allowed / forbidden paths
- ALLOWED: `supabase/migrations/0012_m15_*.sql` (new), `tools/kca/decisions.py`
  (`cmd_approve`), `tools/kca/agent/permission_policy.py` (read path),
  `tests/test_m15_*.py` (or extend the decisions test module).
- FORBIDDEN: submit-step files, `tools/kca/kg.py`, schema files for
  submission_format (T003).

## Permissions
- LOCAL_WRITE (Supabase) ALLOWED; pooler needs `dangerouslyDisableSandbox=true`.
- No real Kaggle / LLM.

## Closeout format
```
M15-T004 closeout
  Migration: 0012_m15_*.sql adds human_decisions.approved_by_user_id uuid NULL (FK to auth.users deferred — documented)
  Populate: kca decisions approve writes calling identity
  Resolver: permission_policy.py reads column for owner-only; NULL-tolerant
  Back-compat: existing rows stay NULL (verified)
  Tests: populate path + NULL-tolerant path
  pytest / ruff: <X> passed; clean; migration applied to cloud
  Acceptance: PASS
  Next: M15-T005 (profile_fallback event)
```

## Related issues
- #60 (ADR-0018 F2 — `approved_by_user_id` FK on `human_decisions`).

## Stop condition
Stop after 60 turns. HALT and ask if:
- The calling identity is not resolvable from the current Decision API token
  (no per-user identity exists pre-auth) — surface it; the populate path may
  write NULL + a documented interim until auth lands.
