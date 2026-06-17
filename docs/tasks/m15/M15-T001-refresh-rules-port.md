# M15-T001: port `kca competition refresh-rules` off removed `competition_view` (issue #78)

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Port the competition-rules fetch off the removed `kaggle.api.competition_view`
to the current Kaggle API surface so `kca competition refresh-rules`
auto-ingests limits again on kaggle 2.0.x. Keep the M14-T009 graceful
degradation path for genuinely-unsupported clients.

Sequenced **early** so the T007 live run gets real `max_daily_submissions` /
`max_concurrent_pushes` / deadline instead of operator-set DB values.

Assumes **M15-T000 closeout is PASS**.

## Read first
1. M15-T000 closeout (ADR-0020 addendum).
2. Issue #78 (acceptance criteria — pin to the issue body).
3. `tools/kca/db.py` — `_fetch_competition_view` (~2787), `_map_competition_view`
   (~2818), `KaggleApiUnsupported` (~161), `refresh_competition_rules`.
4. `tools/kca/competition.py` — `cmd_refresh_rules` (~92).
5. `tests/test_m14_db.py` — `test_fetch_competition_view_unsupported_api_degrades`,
   `test_cmd_refresh_rules_degrades_cleanly_on_unsupported_api` (the degradation
   regression tests to preserve).

## Scope
1. Replace the `competition_view` call in `db._fetch_competition_view` with a
   current Kaggle API path (e.g. `competitions_list` filtered to the slug, or
   the REST client) that returns the fields `_map_competition_view` needs
   (max daily submissions, deadline, etc.).
2. Keep `_map_competition_view` writing the same `competitions` columns; adjust
   only the field extraction to the new payload shape.
3. Preserve the `KaggleApiUnsupported` degradation path: when the new surface is
   also absent on a client, `cmd_refresh_rules` still emits the
   `{"ok": false, "error_code": "KAGGLE_API_UNSUPPORTED", "degraded": true, ...}`
   envelope rather than an AttributeError traceback.

## Non-goals
- No submit-step work (T002), no schema change, no new CLI verbs.
- No multi-competition bulk refresh — single-slug refresh only, as today.

## Acceptance criteria
- `kca competition refresh-rules --slug <slug>` auto-ingests limits on
  kaggle 2.0.x (no `competition_view` AttributeError).
- The existing degradation path remains for genuinely-unsupported clients
  (the two M14-T009 regression tests still pass, adapted to the new surface).
- `_map_competition_view` still writes the same `competitions` columns; existing
  rows are not corrupted.
- `ruff check .` / `ruff format --check .` clean; no pytest regressions.

## Allowed / forbidden paths
- ALLOWED: `tools/kca/db.py` (`_fetch_competition_view` / `_map_competition_view`
  / `refresh_competition_rules`), `tools/kca/competition.py`
  (`cmd_refresh_rules`), `tests/test_m14_db.py` (+ new test fixtures).
- FORBIDDEN: `supabase/migrations/**`, `tools/kca/kg.py`, submit-step files.

## Permissions
- No real Kaggle call required for tests (mock the new API surface). A single
  live `refresh-rules` against the target slug may be run during T007 only,
  with `dangerouslyDisableSandbox=true` (network out to `kaggle.com`).
- LOCAL_WRITE (Supabase) ALLOWED for the column writes.

## Closeout format
```
M15-T001 closeout
  Ported: db._fetch_competition_view off competition_view → <new surface>
  Mapping: _map_competition_view writes same columns; verified
  Degradation: KaggleApiUnsupported path preserved; M14-T009 tests adapted + green
  refresh-rules: auto-ingests limits on kaggle 2.0.x (mocked test)
  pytest / ruff: <X> passed; clean
  Acceptance: PASS
  Next: M15-T002 (explicit submit step)
```

## Related issues
- #78 (port refresh-rules off removed `competition_view`).

## Stop condition
Stop after 60 turns. HALT and ask if:
- No current Kaggle API surface exposes the rule fields the columns need —
  surface the gap; the degradation path may remain the only option and that
  becomes a documented deviation.
- The new payload shape conflicts with the existing `competitions` column
  semantics — pin the conflict before changing the schema (schema changes are
  out of this task's scope).
