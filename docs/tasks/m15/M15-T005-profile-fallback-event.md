# M15-T005: `profile_fallback` event in `permission_policy.py` (issue #61 — ADR-0018 F3)

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Emit a structured `profile_fallback` event in `agent_job_events` whenever the
policy resolver falls back from a `competition_type`-specific profile to the
default profile (because the type-specific YAML doesn't exist), so the
silent-fallback drift becomes observable. Observability fix; no functional
change to resolution.

Independent of T001/T002 — runs in any order within the ADR-0018 hardening group.

## Read first
1. Issue #61 (acceptance criteria — pin to the issue body).
2. `docs/adr/0018-generalized-competition-type.md` §"Resolver fallback contract".
3. `tools/kca/agent/permission_policy.py` —
   `_resolve_profile_for_competition_type` (~101), `resolve_for_skill` (~125)
   (the fallback path added in M12 that does NOT emit an event today).
4. `tools/kca/db.py` — `append_job_event` (~762) (reuse for the emit).
5. `supabase/migrations/0003_m3_worker.sql:34` (`agent_job_events` shape).
6. `tests/test_m12_policy.py` (where the new test lands).

## Scope
1. When `_resolve_profile_for_competition_type` falls back (the
   `competition_type` profile file is missing), emit one `agent_job_events` row
   via `db.append_job_event` with:
   - `event_type='profile_fallback'`
   - `data` jsonb: `{"competition_type": "<type>", "intended_profile":
     "<type>-runner", "actual_profile": "default", "operation": "<op>"}`
2. **Dedupe** once per fallback per job (no repeated rows within a single job).
3. **Thread `job_id`** into the resolver so it can attribute the event.

## Non-goals
- No change to the fallback resolution itself (still falls back transparently).
- No new migration (`agent_job_events` already exists). No change to other
  event_types.

## Acceptance criteria
_Pinned to issue #61:_
- When the resolver falls back (profile file for `competition_type` missing),
  it writes one `agent_job_events` row with `event_type='profile_fallback'` and
  the documented `data` jsonb.
- Event fires once per fallback per job (deduplicated within a job).
- The reviewer agent sees the event in the audit trail.
- Unit test `tests/test_m12_policy.py::test_fallback_emits_event` covers a
  missing-profile-file run.
- `ruff check .` / `ruff format --check .` clean.

## Allowed / forbidden paths
- ALLOWED: `tools/kca/agent/permission_policy.py` (emit + `job_id` threading),
  `tools/kca/db.py` (only if `append_job_event` needs a thin wrapper — prefer
  reuse as-is), `tests/test_m12_policy.py`.
- FORBIDDEN: `supabase/migrations/**`, submit-step files, `tools/kca/kg.py`.

## Permissions
- LOCAL_WRITE (Supabase) ALLOWED for the event write in tests.
- No real Kaggle / LLM.

## Closeout format
```
M15-T005 closeout
  Emit: _resolve_profile_for_competition_type falls back → agent_job_events row event_type=profile_fallback
  data jsonb: {competition_type, intended_profile, actual_profile=default, operation}
  Dedupe: once per fallback per job (verified)
  job_id: threaded into resolver
  Test: tests/test_m12_policy.py::test_fallback_emits_event green
  pytest / ruff: <X> passed; clean
  Acceptance: PASS
  Next: M15-T006 (Supabase parity / retire local Docker)
```

## Related issues
- #61 (ADR-0018 F3 — `profile_fallback` event_type in `permission_policy.py`).

## Stop condition
Stop after 60 turns. HALT and ask if:
- Threading `job_id` into the resolver requires changing a call site outside
  `permission_policy.py` in a way that ripples into unrelated resolution paths —
  pin the call sites and ask before a broad signature change.
