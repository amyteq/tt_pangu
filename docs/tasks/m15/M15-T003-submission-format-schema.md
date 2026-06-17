# M15-T003: jsonb type-check for `competitions.submission_format` (issue #59 — ADR-0018 F1)

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Add a JSON-Schema type-check per `competition_type` for the
`competitions.submission_format` jsonb so per-platform payloads can't drift into
arbitrary shapes. The validator runs at read time and **logs-and-falls-back
permissively** on failure (never crashes the worker), per the ADR-0018
resolver-fallback discipline.

Independent of T001/T002 — can run in any order within the ADR-0018 hardening
group (T003/T004/T005).

## Read first
1. Issue #59 (acceptance criteria — pin to the issue body).
2. `docs/adr/0018-generalized-competition-type.md` §"Migration impact" +
   §"Resolver fallback contract".
3. `docs/evidence/m12/t001/discovery/design-red-team.md` (open_disagreement #1 —
   the untyped-jsonb drift risk this closes).
4. `supabase/migrations/0009_m12_competition_type_teams.sql` (defines the column)
   + `supabase/migrations/0011_m14_goal_loop.sql:71` (`submission_format jsonb`).
5. `tools/kca/submission_checklist.py` (where the validator helper lands; current
   `_dedup_format_keys` + `build_checklist` handling of submission_format).

## Scope
1. **Schema files** — one JSON-Schema per `competition_type` under
   `tools/kca/schemas/submission_format/`:
   `kaggle.json`, `devpost.json`, `hackathon_devpost.json`, `ctf.json`,
   `generic.json` (the ADR-0018 enum literals). New directory.
2. **Validator helper** in `tools/kca/submission_checklist.py` that validates
   `competitions.submission_format` against the matching schema on read, keyed
   by the row's `competition_type`.
3. **Permissive fallback**: validation failures log a warning and fall back to
   the existing permissive behaviour — never raise / crash the worker.
4. **Tests** `tests/test_m12_submission_format_schema.py` covering valid +
   invalid payloads per type; confirm existing M11/M12 rows pass (or update
   them).

## Non-goals
- No DB migration (the column already exists). No write-time enforcement — read
  time validation only. No change to ADR-0018's enum.

## Acceptance criteria
_Pinned to issue #59:_
- A JSON-Schema definition per `competition_type` under
  `tools/kca/schemas/submission_format/` (one file per type).
- A validator helper in `tools/kca/submission_checklist.py` validates
  `competitions.submission_format` against the matching schema on read.
- Validation failures do NOT crash the worker — log a warning + fall back to
  permissive behaviour (per ADR-0018 §"Resolver fallback contract").
- Unit tests under `tests/test_m12_submission_format_schema.py` cover valid +
  invalid payloads per type.
- M12 / M11 existing rows pass validation (or are updated).
- `ruff check .` / `ruff format --check .` clean.

## Allowed / forbidden paths
- ALLOWED: `tools/kca/schemas/submission_format/*.json` (new),
  `tools/kca/submission_checklist.py`,
  `tests/test_m12_submission_format_schema.py`.
- FORBIDDEN: `supabase/migrations/**`, `tools/kca/kg.py`, autonomy / submit files.

## Permissions
- No real Kaggle / LLM. LOCAL_WRITE (Supabase) read-only for row validation in
  tests (or fixtures).

## Closeout format
```
M15-T003 closeout
  Schemas: tools/kca/schemas/submission_format/{kaggle,devpost,hackathon_devpost,ctf,generic}.json
  Validator: submission_checklist.py validates on read, keyed by competition_type
  Fallback: invalid payload → warning + permissive; worker never crashes (test)
  Tests: tests/test_m12_submission_format_schema.py valid+invalid per type
  Existing rows: M11/M12 rows pass
  pytest / ruff: <X> passed; clean
  Acceptance: PASS
  Next: M15-T004 (approved_by_user_id FK)
```

## Related issues
- #59 (ADR-0018 F1 — jsonb type-check for `submission_format`).

## Stop condition
Stop after 60 turns. HALT and ask if:
- An existing M11/M12 row fails its schema and the correct fix is ambiguous
  (tighten the schema vs migrate the row) — pin the row and ask.
