---
adr: "0018"
title: "Generalized competition_type — folded enum on competitions"
status: Accepted
date: 2026-06-09
milestone: M12
supersedes: none
references:
  - docs/adr/0006-configurable-approval-gates.md
  - docs/adr/0009-competition-repo-strategy.md
  - docs/adr/0015-memory-promotion-model.md
  - docs/evidence/m12/t001/discovery/legacy-archaeologist.md
  - docs/evidence/m12/t001/discovery/requirements-skeptic.md
  - docs/evidence/m12/t001/discovery/design-red-team.md
---

# ADR-0018: Generalized `competition_type` — folded enum on `competitions`

## Status

Accepted (M12-T001, 2026-06-09).

## Context

`docs/milestones/README.md` §M12 commits the platform to validating a non-Kaggle hackathon-submission path (Devpost) on the picked target `h01` (docs/evidence/m12/t000-candidates.md:14). M11 will reuse the same `competitions` surface for CTF challenges. M9 and M10 already established two Kaggle code paths (CSV submit and kernel push) against the existing Kaggle-only schema (supabase/migrations/0004_m4_competition_repo.sql:14–18) and ADR-0006 approval-gate hierarchy.

The Discovery / Debate Gate (`docs/milestone-loop-protocol.md` §7, `docs/architecture/discovery-debate-gate.md`) ran three role-isolated reports against the Kaggle-specific surfaces:

- `docs/evidence/m12/t001/discovery/legacy-archaeologist.md` — names the ten Kaggle-specific dimensions the generalization touches, the multi-Kaggle-account legacy precedent (`tools/legacy/kkr.py:541`), the ADR-0006 four-level hierarchy, the untyped `competition_policy` jsonb surface, and the per-skill profile loader at `tools/kca/agent/permission_policy.py:79–88`.
- `docs/evidence/m12/t001/discovery/requirements-skeptic.md` — surfaces six explicit unknowns including the `'devpost'` vs `'hackathon_devpost'` boundary, the team-scoped "owner" question, and the silent-fallback foot-gun in the resolver.
- `docs/evidence/m12/t001/discovery/design-red-team.md` — debates the three required alternatives (A folded enum / B separate table / C denormalised jsonb) plus one supplementary alternative (D, hybrid enum + CHECK), names the dropped capabilities, and scores the four long-term-cost axes.

The product constraints the synthesis must satisfy:

1. **Backwards-compatible.** Every existing Kaggle row (M9 / M10 baselines) must resolve its approval gates identically before and after migration 0008. ADR-0006's four-level hierarchy is **preserved, not superseded**.
2. **M11 reuse without a second migration.** The enum must carry a `'ctf'` value from day one (docs/tasks/m12/M12-T001-discovery-debate-gate.md:81–83).
3. **Audit-traceable foot-gun rejection.** The Discovery / Debate Gate exists because the original `tools/legacy/kkr.py` migration lost multi-account semantics silently (`docs/meeting-notes/2026-05-24-r3.md` §6, referenced from `docs/architecture/discovery-debate-gate.md:18–22`). ADR-0018 must NOT introduce a new silent-fallback path.
4. **Additive, not renaming.** "Renaming any of the existing Kaggle-specific surfaces" is explicitly out of scope (docs/milestones/m12/loop-prompts.md:116). `kaggle_submit` / `kernel_push` keep their names; the new `devpost_submit` is additive.

## Decision

### Alternative chosen: **A — Folded `competition_type` enum on the existing `competitions` table.**

The full text of the three alternatives the red team scored lives in `docs/evidence/m12/t001/discovery/design-red-team.md` §alternatives. Summary:

| Axis (one-sentence summary) | A — folded enum | B — separate table | C — jsonb discriminator |
|---|---|---|---|
| Implementation cost | low: 1 ENUM + 1 ALTER + 1 backfill | high: net-new table + duplicate FK forest | trivial: jsonb edit only |
| M11 reuse cost | trivial: `ALTER TYPE … ADD VALUE 'ctf'` is already in the M12 enum | high: M11 ships a third table | trivial: jsonb edit only |
| Backwards-compat | safe: DEFAULT 'kaggle' + UPDATE; resolver behaviour unchanged | safe: Kaggle table untouched | safe: existing rows omit `type` → treated as Kaggle |
| UI churn | low: one column added, two new pages read it | high: every Kaggle UI query must JOIN-or-NOT depending on type | low but unsafe: no `\d` visibility of the type |
| Audit / safety | medium: untyped jsonb keys remain a known foot-gun (open disagreement #1) | high: DB-level type safety, but worker code complexity is high | **low: silent-fallback class of bug** (red team §blast_radius) |

**Why A wins.** Alternative C's blast radius is the canonical Discovery / Debate Gate failure mode — a silent-fallback path that approves the wrong gate without surfacing the mistake (red-team §blast_radius); that alone disqualifies it for an architectural decision whose entire motivation is preventing this class of bug. Alternative B is structurally clean but multiplies the worker code surface and forces every `experiments` / `experiment_runs` / `submissions` FK to learn which parent table it is FK'd to — that cost lands in M12-T006 and every future task. Alternative A's two known weaknesses (the untyped jsonb surface and the silent-fallback in the resolver) are addressable without a schema change:

- The jsonb weakness is captured as **Open disagreement #1** (red team §open_disagreements) and filed as a `type:tech-debt` follow-up at M12 close.
- The silent-fallback weakness is captured as **Open disagreement #4** and is addressed *in this ADR* by §"Resolver fallback contract" below — the resolver MUST emit a structured warning event on every type-specific profile miss.

### Schema (lands in M12-T002, migration 0008)

```sql
CREATE TYPE competition_type_enum AS ENUM
  ('kaggle', 'devpost', 'hackathon_devpost', 'ctf', 'generic');

ALTER TABLE competitions
  ADD COLUMN competition_type competition_type_enum NOT NULL DEFAULT 'kaggle',
  ADD COLUMN deadline          timestamptz NULL,
  ADD COLUMN submission_format jsonb       NULL;

CREATE INDEX IF NOT EXISTS idx_competitions_type
  ON competitions(competition_type);

CREATE TABLE IF NOT EXISTS teams (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS team_memberships (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  team_id     uuid NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL,
  role        text NOT NULL DEFAULT 'member',
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (team_id, user_id)
);
```

The enum literal `('kaggle', 'devpost', 'hackathon_devpost', 'ctf', 'generic')` is **non-negotiable** for this ADR: `'ctf'` is reserved so M11 can plug in without a second migration (docs/tasks/m12/M12-T001-discovery-debate-gate.md:82–83), and `'generic'` is the fallback for future hackathon platforms (HackerEarth, MLH, Devfolio) that may land in M12.x or M13. No sixth value ships in M12; expansion requires a fresh ADR (docs/tasks/m12/M12-T001-discovery-debate-gate.md:111–113).

#### Enum value semantics (one sentence each — addresses skeptic §explicit_unknowns)

- `'kaggle'` — a Kaggle competition with CSV-submit and/or kernel-push; ADR-0006 default-allow gates apply unless overridden.
- `'devpost'` — the Devpost platform generally; non-hackathon Devpost listings (challenges, judging-only events) belong here.
- `'hackathon_devpost'` — a Devpost-hosted event that follows the hackathon-format submission shape: README + demo + source + architecture diagram. M12-T002 may write either `'devpost'` or `'hackathon_devpost'` for the picked `h01` target; the picking happens in T003 once the Devpost page is fetched.
- `'ctf'` — reserved for M11. No M12 code paths read or write this value; the M12 default profile DOES NOT carry `ctf_*` op entries, so a stray `'ctf'` row in M12 falls through to `_tool_default_decision(operation) == 'ask'` (skeptic §side_effects.6; red-team §open_disagreement.5).
- `'generic'` — fallback for unrecognised competition platforms; resolver behaves as if the bound profile were `default.yaml`.

### Policy resolver shape (lands in M12-T002)

The resolver in `tools/kca/agent/permission_policy.py:41–51` gains a `competition_type` argument (default `'kaggle'` for backwards-compat). ADR-0006's four-level hierarchy is preserved exactly:

```
per-job  >  competition (competition_policy jsonb) >  project >  platform defaults
```

The competition layer gains a sub-layer routing on `competition_type`:

```
resolve(operation, mode, *, competition_type):
    profile_name = {
        'kaggle':            'competition-runner',     # M9 / M10 unchanged
        'devpost':           'hackathon-runner',       # ships M12-T004
        'hackathon_devpost': 'hackathon-runner',       # same profile as 'devpost'
        'ctf':               'default',                # M11 will ship 'ctf-runner'
        'generic':           'default',
    }[competition_type]
    if not (PERMISSIONS_ROOT / f'{profile_name}.yaml').is_file():
        # Structured-warning fallback (red team open_disagreement #4)
        emit_event(
            tool='policy_resolver',
            event='profile_fallback',
            from_type=competition_type,
            requested_profile=profile_name,
            resolved_profile='default',
        )
        profile_name = 'default'
    return load_policy(profile_name).resolve(operation, mode=mode)
```

#### Resolver fallback contract (addresses red-team open_disagreement #4)

When the type-specific profile is missing, the resolver MUST:

1. Emit a single structured event with `tool='policy_resolver'`, `event='profile_fallback'`, the requested profile name, and the resolved profile name. This is the audit-log signal that the silent-fallback class of bug is now visible.
2. Resolve against `default.yaml`. This preserves the M9 / M10 regression behaviour.
3. Never raise. A missing profile is an *operational* condition (the profile may not have shipped yet for a future type), not a *correctness* condition.

The event lands in `agent_job_events` via the existing audit path; no new column is required.

### Approval-gate vocabulary additions (lands in M12-T004)

The `hackathon-runner.yaml` profile (M12-T004 scope, not this ADR) ships three new op entries:

| Op | M12 default | Reason |
|---|---|---|
| `devpost_submit` | `ask` | External hackathon submission; analog of `kaggle_submit`'s ADR-0006 conservative default (ADR-0006 is default-allow for `kaggle_submit` but ADR-0018 overrides per-type; see §"Migration impact" below). |
| `demo_upload` | `ask` | Public artifact publication; analog of `kernel_push`. Not used in M12 (reserved for M12.x demo-video flow). |
| `team_invite` | `deny` | Out of M12 scope (read-only team membership only; docs/tasks/m12/M12-T001-discovery-debate-gate.md:91–92). |

The `default.yaml` profile gets no new entries — unknown ops continue to fall through to `_tool_default_decision(operation) == 'ask'` per `tools/kca/agent/permission_policy.py:50–51`.

### Team-scoped operation rules

M12 ships **owner-only** approval for every gate that fires on a `competition_type='devpost'` or `'hackathon_devpost'` row:

- A `human_decisions` row inserted for a team-scoped competition records the row owner (the `created_by_user_id` on the `competitions` row, if present; if not present, the first-listed `team_memberships.user_id` for the team).
- Any `team_memberships.user_id` MAY view the pending decision; only the owner MAY transition it to `approved` or `denied`.
- This rule is documentation-only in M12 (the resolver does not enforce it; the `kca decisions approve --id <id>` CLI does not authenticate). Skeptic §personas_and_accounts.6 flagged this as a weakness; red-team open_disagreement #2 filed it as a P1 follow-up for M12-T007.

A future milestone (M12.x or M13) MAY relax the rule per-op (e.g. let a non-owner member trigger `submission_checklist` reads but not `devpost_submit`) by adding an `allowed_for_roles: ['owner', 'member']` clause to each `PolicyRecord` in `tools/kca/agent/permission_policy.py:25–30`. ADR-0018 does NOT ship this relaxation.

### Migration impact (concrete; lands in M12-T002)

| Existing rows | Backfill |
|---|---|
| `competitions` rows for M9 (`spaceship-titanic`), M10 (`tpu-getting-started`), any other Kaggle slugs registered before 2026-06-09 | `UPDATE competitions SET competition_type='kaggle' WHERE competition_type IS NULL` (run before the `NOT NULL` is enforced if the migration uses two-phase ALTER; one-phase ALTER with `DEFAULT 'kaggle'` plus `NOT NULL` is also acceptable per skeptic §explicit_unknowns.2). |
| `experiments`, `experiment_runs`, `submissions` rows | No backfill needed; they FK to `competitions(id)` and inherit the parent's `competition_type` at query time. |
| `competitions.competition_policy` jsonb | Unchanged for Kaggle rows. New Devpost rows MAY carry per-row gate overrides per ADR-0006 §"Per-competition override"; ADR-0018 does not constrain the key schema (red team open_disagreement #1 flags this as tech-debt). |

| `.kca/permissions/*.yaml` profile changes (M12-T004 scope) | Add `hackathon-runner.yaml` with `devpost_submit`, `demo_upload`, `team_invite` entries per the table above. `default.yaml`, `competition-runner.yaml`, `permissive-dev.yaml` are **unchanged**. |
| ADR-0006 default `kaggle_submit: false` (allow) | **Preserved** for `competition_type='kaggle'`. ADR-0006 is referenced, not superseded. |

### Resolver behaviour for the M9 / M10 baseline (regression check)

- A `competition_type='kaggle'` row with no `competition_policy.approval_gates` override resolves `kaggle_submit` to `ask` via `competition-runner.yaml:2–9` (existing behaviour, M9 / M10 baseline).
- A `competition_type='kaggle'` row with `competition_policy = {"approval_gates": {"kaggle_submit": false}}` resolves `kaggle_submit` to `allow` via the per-competition override (existing ADR-0006 §"Per-competition override" behaviour, M9-T004 used this).
- A `competition_type='devpost'` row resolves `devpost_submit` to `ask` via the new `hackathon-runner.yaml`.
- A `competition_type='devpost'` row with `competition_policy = {"approval_gates": {"kaggle_submit": true}}` resolves `kaggle_submit` to `ask` because the resolver still honours the jsonb override for any op key, *even when the op makes no semantic sense for the type*. Red team open_disagreement #1 flags this as a foot-gun; M12 accepts it as known tech-debt.

## Consequences

- **Positive.** One ALTER and one new column on the existing table; one new permission profile file; the four-level ADR-0006 hierarchy is preserved verbatim; M11 plugs in with `ALTER TYPE … ADD VALUE 'ctf'` (no, the value is already there) plus a `ctf-runner.yaml` profile.
- **Positive.** A `WHERE competition_type='devpost'` query is index-supported (`idx_competitions_type`) for the UI list pages and for telemetry.
- **Positive.** The silent-fallback foot-gun (red-team §blast_radius for Alternative C) is *not* introduced — the resolver emits a structured `profile_fallback` event on every type-specific-profile miss.
- **Negative.** The `competition_policy` jsonb key surface remains untyped; a Devpost row CAN carry `kaggle_submit: true` and the resolver will honour it. **Accepted with rationale** (preserve ADR-0006 hierarchy verbatim; red-team open_disagreement #1 filed as P2 tech-debt follow-up).
- **Negative.** The team-scoped owner-only rule is documentation-only in M12 (no `human_decisions.approved_by_user_id` column). **Accepted with rationale** (M12 ships read-only team membership only per docs/tasks/m12/M12-T001-discovery-debate-gate.md:91–92; red-team open_disagreement #2 filed as P1 follow-up for M12-T007).
- **Negative.** The `'devpost'` vs `'hackathon_devpost'` boundary is defined by submission-shape; if a future Devpost event has a hackathon-shape submission but is mis-categorised as `'devpost'`, the `hackathon-runner.yaml` profile still binds (the resolver maps both to the same profile per §"Policy resolver shape"). **Accepted** — both values route to the same profile in M12, so the boundary is documentation-only.
- **Multi-Devpost-account precedent.** Not solved (red-team §dropped_capabilities). If M12.x or M13 needs it, a `competition_credentials` join table is the structural answer; out of M12 scope.

## Dropped capabilities — disposition

| Red-team §dropped_capabilities | Preserved? | Where |
|---|---|---|
| Per-Kaggle-owner secret partitioning (`.env.<owner>`) | **Not preserved.** Out of M12 scope; legacy only. Flagged for future ADR. |
| Per-competition `competition_policy.approval_gates` key-level type-safety | **Not preserved.** Accepted with rationale; open_disagreement #1 → P2 tech-debt follow-up. |
| `competition_type='devpost'` index for `WHERE competition_type=…` | **Preserved.** ADR-0018 includes `CREATE INDEX idx_competitions_type`. |
| "Row owner" persona for the team-scoped rule | **Partially preserved.** Documentation-only in M12; open_disagreement #2 → P1 follow-up. |
| Multi-Devpost-account precedent | **Not preserved.** Out of M12 scope. |

## Follow-up issues filed at M12-T001 close

- **F1** — Type-check `competition_policy.approval_gates` keys against `competition_type` (red-team open_disagreement #1). Labels: `area:supabase`, `type:tech-debt`, `priority:P2`.
- **F2** — Record `human_decisions.approved_by_user_id` for team-scoped competitions (red-team open_disagreement #2; skeptic §personas_and_accounts.6). Labels: `area:supabase`, `area:worker`, `priority:P1`. Target: M12-T007 design step.
- **F3** — Emit structured `policy_resolver.profile_fallback` event (red-team open_disagreement #4). Labels: `area:worker`, `type:bug`, `priority:P1`. Target: M12-T002 (encoded in this ADR §"Resolver fallback contract").
- **F4** — Ship `ctf-runner.yaml` profile alongside the first M11 CTF code path (red-team open_disagreement #5). Labels: `area:policy`, `area:worker`, `milestone:M11`.

## Cross-references

- ADR-0006 — referenced for the four-level approval-gate hierarchy. **Not superseded.**
- ADR-0009 — referenced for the per-competition repo convention. **Not superseded.** `kaggle-<slug>` repo naming stays for Kaggle rows; Devpost rows MAY use `devpost-<slug>` or `hackathon-<slug>` (M12-T003 scope).
- ADR-0015 — referenced for the YAML front-matter convention used by this ADR.
- `docs/evidence/m12/t001/discovery/{legacy-archaeologist,requirements-skeptic,design-red-team}.md` — the three Discovery / Debate Gate reports this ADR synthesises.
- `docs/architecture/discovery-debate-gate.md` — the gate this ADR's authoring satisfied.
