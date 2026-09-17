# ADR-0016: CTF data model — events, challenges, attempts

## Status

Accepted (M11-T001, 2026-06-09). Lands with `supabase/migrations/0008_m11_ctf.sql` and `src/db/ctf.py`.

Cross-link: [`docs/evidence/m11/discovery/design-red-team.md`](../evidence/m11/discovery/design-red-team.md), [`docs/evidence/m11/discovery/legacy-archaeologist.md`](../evidence/m11/discovery/legacy-archaeologist.md), [`docs/evidence/m11/discovery/requirements-skeptic.md`](../evidence/m11/discovery/requirements-skeptic.md).

## Context

M11 is the first non-Kaggle competition platform on the agent stack. The CTFtime workflow (planning Q&A, `docs/milestones/m11/loop-prompts.md` §at-a-glance) needs persistent, queryable records for three things:

1. **Events** — which CTFtime-listed event we are participating in, when it runs, and where the credentials for it live.
2. **Challenges** — per-event jeopardy items the agent might attempt, each optionally bound to a `ctf_scopes` (migration 0001) authorization row.
3. **Attempts** — every flag submission, accepted or not, with enough identity context that "which credential ran this" is answerable from the row alone.

The pre-existing `ctf_scopes` table from migration 0001 covers authorization (target URLs, local-only flag, expiry). M11 adds the three tables above; `ctf_scopes` is referenced via an FK from `ctf_challenges.scope_id` but is otherwise untouched.

## Decision

### 1. Multi-event identity model

```
projects (0001)
  └─ ctf_events  (slug UNIQUE globally; per-project FK)
       └─ ctf_challenges  (UNIQUE (event_id, slug))
            └─ ctf_attempts  (FK to challenge; FK to experiment_runs.id)
```

- `ctf_events.slug` is **globally unique** so that `~/.ctf/<slug>.json` credential paths are unambiguous and so the `kca ctf event` subcommands can address events by slug alone (no `--project` flag for the common case).
- `(event_id, slug)` is unique on `ctf_challenges` so challenge slugs scope per-event — two events can both have `web-1`.
- `ctf_challenges.scope_id` is nullable and `ON DELETE SET NULL`: a challenge can pre-exist its authorization row (T004 creates challenges before T002 wires the full scope policy), and deleting a stale scope must not cascade-delete challenge history.
- `ctf_attempts.run_id` FK to `experiment_runs(id)` is nullable and `ON DELETE SET NULL` so attempts survive run cleanup.

### 2. `credentials_ref` is a path hint, not a value

`ctf_events.credentials_ref` is a `text` column intended to store a path hint such as `~/.ctf/picoctf-2024.json` or an env-var prefix such as `CTF_PICOCTF_2024_`. It **never** holds the credential value itself.

The Python helper `register_event` validates the input and refuses any string containing the heuristic markers `= { "token" Bearer  sk- eyJ`, which catch the common shapes of accidentally-pasted tokens, JSON blobs, env-var key=value pairs, and JWTs. This is a defense-in-depth measure on top of:

- the hook-layer carve-out for `~/.ctf/*` reads (M11-T002 owns `.claude/hooks/guard_tool.py`),
- the M11-T008 audit-grep test (no `~/.ctf/*` content in any test run's stdout/stderr),
- and the dev-phase secret denylist enforced at the harness layer.

### 3. `flag_length` recorded, `flag_value` NOT recorded

`ctf_attempts.flag_length` stores the integer length of the submitted flag. The flag *value* is never accepted as a function parameter and never persisted to any column. This invariant exists because:

- A future "flag dictionary leak" failure mode (the row-level analogue of the kkr.py output-leakage gap, see [legacy-archaeologist §3](../evidence/m11/discovery/legacy-archaeologist.md)) is structurally prevented when the DB cannot return the value.
- Operators who need to debug a wrong-flag submission can still reconstruct the flag from the agent's local audit log (`agent_tool_audit` / `experiment_runs` artifacts) under explicit approval — that path is gated, the DB path is not.

The Python helper `record_attempt` additionally refuses to store a `response_excerpt` that contains the literal phrase "flag length" alongside a non-null `flag_length` column — this catches the failure mode where the event API's error body itself echoes "incorrect flag length: 42", which combined with `flag_length=42` would let any reader infer length without the row's column. Callers must pre-scrub the excerpt; the excerpt is also truncated to **256 chars**.

### 4. Multi-account / team identity on the attempt row

Per the T000 design-red-team report ([§dropped_capabilities/2 + §open_disagreements/2](../evidence/m11/discovery/design-red-team.md)), the kkr.py M9.4 replay surfaced a critical gap: a submissions table without an explicit credential-identity column cannot answer "which credential made this submission" after the fact. The same gap in `ctf_attempts` would re-incarnate the failure mode.

M11-T001 therefore adds **two columns to `ctf_attempts`** beyond the task-spec skeleton:

| Column          | Type | Nullable | Why                                    |
|-----------------|------|----------|----------------------------------------|
| `event_account` | text | yes      | The username / e-mail / handle that authenticated to the event API at submit time. |
| `team_id`       | text | yes      | The team identifier reported back by the event API (if the event has team scoring). |

Both columns are populated by `record_attempt(... event_account=..., team_id=...)` and surfaced on `list_attempts`. They are nullable so single-account events and pre-T007 dry-runs do not need to lie.

### 5. Retention policy for failed attempts

Default: **keep indefinitely**. The attempt-level redaction lives in `response_excerpt` (256-char cap, callers pre-scrub). There is no TTL job. Rationale:

- Failed-attempt history is load-bearing for post-event audit ("did the agent try the same wrong flag 50 times?") and rate-limit evidence ("the event API returned 429 on the 3rd attempt").
- The columns we keep are all low-cardinality / low-volume; the whole table is small relative to `agent_tool_audit`.
- A future retention policy may add `ctf_attempts.expires_at` plus a cron, but that decision is M12+ scope (see open question 1).

### 6. RLS enabled, no policies yet

All three tables `ENABLE ROW LEVEL SECURITY` but ship without policies, mirroring `ctf_scopes` in migration 0001. The kca CLI connects as `postgres` (RLS bypassed); UI / supabase-js callers will need policies before they can read these tables. Policies are deferred until the auth model lands (see ADR follow-ups in M12 / M13).

## Consequences

### Pros

- Schema is the smallest delta that addresses the kkr.py failure mode structurally (`event_account` + `team_id` on every attempt).
- `flag_value` is not in the schema, so the leak-by-DB-query path is closed by construction.
- All three tables are FK-cascaded from a single parent (`projects → ctf_events → ctf_challenges → ctf_attempts`), so cleanup is a single `DELETE FROM ctf_events WHERE …`.

### Cons / known limits

- The schema carries the most cognitive load of the four alternatives surfaced in the design-red-team report (three new tables + the existing `ctf_scopes` + a FK back to `projects`, not `competitions`). Alternative 1 (`competition_type` discriminator on the existing `competitions` table) would have been zero new tables. We accept the cost in exchange for a clean CTF-only query surface during M11; see open question 1 below.
- The `category` column is a CHECK-constrained string, not a Postgres ENUM. This is consistent with the precedent in 0007 (`decision` CHECK on `agent_tool_audit`) and avoids the `ALTER TYPE … ADD VALUE` migration headache when a new category (e.g. `hardware`) shows up. The cost is per-row CHECK enforcement rather than catalog-level type safety; downstream analytics use string comparisons.
- `credentials_ref` validation is a Python-layer heuristic, not a DB CHECK. A motivated caller writing raw SQL can still insert a credential value into the column. The hook layer and the M11-T008 audit-grep test are the two other layers that catch this; the DB is not the only line of defense.

## Open questions (deferred)

1. **Overlap with M12 `competition_type`.** M12 is already planning a `competition_type` discriminator on the existing `competitions` table (see `docs/milestones/README.md` §M12 and [design-red-team §alternatives/1](../evidence/m11/discovery/design-red-team.md)). When M12 lands, the three M11 tables may be folded into `competitions` / `competition_subtasks` / `submissions` rather than continuing to live as a parallel trinity. **This ADR is M11-scoped and does not block on the M12 decision.** A follow-up ADR / issue should capture the migration path at M12 close.
2. **Stable JSON shape for `kca ctf flag submit --json`.** M11-T003 owns the CLI; the JSON shape is not pinned here. If a downstream tool (UI Approval Inbox, T008 audit-grep) needs to parse the output, that contract belongs in a T003 / T009 amendment.
3. **Per-event rate-limit metadata.** The design-red-team report surfaced "per-challenge attempts-per-hour" as a dropped capability. M11 records attempts after the fact only; a pre-submit gate that consults a per-challenge counter is deferred to M11 follow-ups or M12+.
4. **Subprocess-isolated credential reads.** The credential file is currently read in-process by the worker (see [design-red-team §open_disagreements/6](../evidence/m11/discovery/design-red-team.md)). A future spike may move the read into a dedicated subprocess so the parent worker never holds the token in-process. Not blocking M11.

## Alternatives considered

See [`docs/evidence/m11/discovery/design-red-team.md` §alternatives](../evidence/m11/discovery/design-red-team.md) for the full red-team analysis. In brief:

1. **Reuse `competitions` with a `competition_type` discriminator** — zero new tables, but reshapes the Kaggle-shaped `submissions` table. Deferred to M12 (see open question 1).
2. **Scope-as-policy: rich `ctf_scopes` + `competitions`** — one new table instead of three; reuses the kaggle_submit reviewer-gate chain. Rejected for M11 because it tangles authorization and identity into a single table.
3. **Stateless / file-backed CTF identity, DB only for attempts** — events / challenges as YAML in `data/ctf/`; only attempts hit the DB. Rejected because cross-event analytics becomes a filesystem walk and FK integrity for `ctf_attempts.event_slug` cannot be enforced.
4. **Per-event sandbox with no shared identity** — each event in its own short-lived docker network with mounted credential. Strongest isolation, but doubles per-job latency and complicates OTEL. Deferred to M13+ if the threat model demands it.

## References

- [Migration `0008_m11_ctf.sql`](../../supabase/migrations/0008_m11_ctf.sql)
- [`src/db/ctf.py`](../../src/db/ctf.py) — DB helpers
- [`tests/test_m11_db.py`](../../tests/test_m11_db.py) — smoke tests
- [`docs/evidence/m11/discovery/design-red-team.md`](../evidence/m11/discovery/design-red-team.md)
- [`docs/evidence/m11/discovery/legacy-archaeologist.md`](../evidence/m11/discovery/legacy-archaeologist.md)
- [`docs/evidence/m11/discovery/requirements-skeptic.md`](../evidence/m11/discovery/requirements-skeptic.md)
- [`docs/evidence/m9_4-kkr-replay/legacy-archaeologist.md`](../evidence/m9_4-kkr-replay/legacy-archaeologist.md) §3 — the "owner on the submission row" gap precedent
- [`supabase/migrations/0001_init.sql`](../../supabase/migrations/0001_init.sql) — `ctf_scopes` and base tables
- [ADR-0005](0005-job-taxonomy.md) — `project_kind` enum + platform slugs
- [ADR-0006](0006-configurable-approval-gates.md) — approval-op data shape
