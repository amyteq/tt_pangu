# M12-T001: Discovery / Debate Gate on competition-policy generalization

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Run the Discovery / Debate Gate (`docs/milestone-loop-protocol.md` §7)
on the proposed generalization of the competition-policy layer beyond
Kaggle. The gate's output is three role-isolated reports
(`legacy-archaeologist`, `requirements-skeptic`, `design-red-team`) and
ADR-0018 synthesising them into a concrete `competition_type` schema +
policy-resolver design that M12-T002 implements.

The motivating constraint: M11 (CTF) must be able to reuse this schema
without a second migration. The enum must therefore carry CTF-friendly
values from day one.

## Tag

`arch:` — invokes the Discovery / Debate Gate. Mandatory.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M11 and §M12
3. `docs/milestones/m12/loop-prompts.md` (especially "Discovery / Debate Gate" + "What's in scope")
4. `docs/milestone-loop-protocol.md` §7
5. `docs/architecture/discovery-debate-gate.md`
6. `docs/adr/0006-configurable-approval-gates.md` — the policy hierarchy this generalizes
7. `docs/adr/0009-competition-repo-strategy.md` — competition-repo coupling
8. `docs/adr/0015-memory-promotion-model.md` — recent ADR shape (use as template)
9. `supabase/migrations/0004_m4_competition_repo.sql` — current `competitions` shape
10. `tools/kca/competition.py` — current register / clone / list / info paths
11. `.kca/permissions/default.yaml`, `.kca/permissions/competition-runner.yaml`, `.kca/permissions/permissive-dev.yaml`
12. `src/worker/_types.py::JobPolicy`, `tools/kca/agent/permission_policy.py`, `src/worker/tools.py`

## Scope

1. Confirm M12-T000 is closed and a `Picked slug:` line exists on the
   closing issue. If not, halt — T001 cannot run without a concrete
   regression target.
2. Invoke the three Discovery / Debate Gate subagents in this order
   (`docs/milestone-loop-protocol.md` §7 step 1–3):
   a. `legacy-archaeologist` — read the Kaggle-specific surfaces in
      scope (`competitions` schema, `tools/kca/competition.py`,
      `tools/kca/kg.py`, ADR-0006, ADR-0009, the kaggle-experiment-loop
      skill, the three `.kca/permissions/*.yaml` profiles, the
      Kaggle-only fields on `submissions` / `experiment_runs`). Surface
      hidden semantics: multi-Kaggle-account precedent from
      `tools/legacy/kkr.py`; per-competition policy-overrides; the
      kaggle-CLI auth shape that `M9-T000` deviation worked around.
   b. `requirements-skeptic` — produce ≥5 sharp questions across ≥3
      categories. Categories MUST include at least:
      `hidden_constraints` (team identity, deadline windows,
      rate-limit semantics), `personas_and_accounts` (single-user vs.
      team submissions; agent-only vs. agent-and-human), `side_effects`
      (one real Devpost submission vs. draft; rollback if the
      submission is rejected), `rollback`, plus an `explicit_unknowns:`
      section.
   c. `design-red-team` — produce ≥3 alternative designs for the
      generalization. Required alternatives (verbatim names — the
      red team may add more): "A. Folded `competition_type` enum on
      existing `competitions` table"; "B. Separate `hackathon_competitions`
      table"; "C. Denormalised `competition_policy` jsonb on
      `competitions` with no enum". For each, score on the four cost
      axes (implementation, M11 reuse, backwards-compat, UI churn) and
      name ≥1 dropped capability with file:line evidence. Output an
      `actionable open_disagreements:` section.
3. Attach all three reports to
   `docs/evidence/m12/t001/discovery/{legacy-archaeologist,requirements-skeptic,design-red-team}.md`.
   Each MUST carry its canonical acceptance line **verbatim** (per
   `docs/architecture/discovery-debate-gate.md`).
4. Verify each acceptance line byte-for-byte. A missing acceptance
   line is a task FAIL — re-invoke the agent, do not patch by hand.
5. Synthesise the three reports into
   `docs/adr/0018-generalized-competition-type.md`. The ADR MUST:
   - Pick one of the three alternatives (default expectation: A —
     folded enum — unless the red team's evidence makes B or C
     decisively better; the ADR must explain the trade-off).
   - Define the enum values verbatim:
     `('kaggle', 'devpost', 'hackathon_devpost', 'ctf', 'generic')`.
     The `ctf` value MUST appear so M11 can reuse the schema without
     a second migration.
   - Define the policy-resolver shape: route on `competition_type`;
     fall back to the existing default profile when no type-specific
     profile is found; per-job override still wins (ADR-0006
     hierarchy preserved).
   - Define team-scoped operation rules: which approval gates can be
     triggered by a non-owner team member; which require the owner.
     M12 ships read-only team membership only, so the ADR may default
     all gates to `owner-only` for now and list a follow-up to relax
     in a future milestone.
   - Reference ADR-0006 + ADR-0009; supersede neither.
   - List concrete migration impact: which existing rows backfill to
     `'kaggle'`, which `.kca/permissions/*.yaml` profiles get new
     entries.
6. Update `PROJECT_STATE.md` to add ADR-0018 to the open-decisions
   list (per `feedback_ci_repair_workflow.md` discipline).
7. Run `grep -nE 'competition_type|hackathon_devpost' docs/adr/0018-*.md`
   to confirm the enum values appear; commit the evidence.

## Non-goals

- Do NOT write `supabase/migrations/0008_*.sql`. That's M12-T002.
- Do NOT edit `src/worker/_types.py` or `permission_policy.py`. That's
  M12-T002.
- Do NOT add new permission profiles. That's M12-T004.
- Do NOT write any code in `tools/kca/devpost.py`. That's M12-T003.
- Do NOT skip the gate to save turns. Missing acceptance lines are a
  hard FAIL.
- Do NOT silently expand the enum beyond the five named values; if a
  sixth value (`benchmark`, `bounty`, etc.) seems needed, document the
  rationale and add it explicitly with the red-team report's blessing.

## Acceptance criteria

- Three Discovery-Debate reports exist under
  `docs/evidence/m12/t001/discovery/`; each carries its canonical
  acceptance line byte-for-byte (verify via `grep -F` against the
  expected strings in `docs/architecture/discovery-debate-gate.md`).
- `docs/adr/0018-generalized-competition-type.md` exists; the enum
  literal `('kaggle', 'devpost', 'hackathon_devpost', 'ctf', 'generic')`
  appears verbatim in the ADR body.
- The ADR picks one of the three alternatives and explains the
  trade-off; the red-team's dropped capabilities are addressed (either
  preserved or explicitly accepted with rationale).
- `PROJECT_STATE.md` lists ADR-0018 under open / recently-resolved
  decisions.
- `python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('docs/adr/0018-generalized-competition-type.md').read_text().split('---',2)[1])"`
  parses the ADR front-matter without error (if the ADR uses YAML
  front-matter per ADR-0015 precedent).
- No code, test, or migration files touched.
- `python -m pytest tests/ -q` still passes.

## Permissions

- `Read` / `Glob` / `Grep` / `WebFetch` allowed (for ADR research).
- `Edit` / `Write` restricted to: `docs/evidence/m12/t001/discovery/**`,
  `docs/adr/0018-generalized-competition-type.md`, `PROJECT_STATE.md`.
- No DB writes. No `kca` write subcommands. No Devpost / Kaggle network
  calls.
- `git commit` / `git push` deferred to T009 closeout.

## Closeout format

```
M12-T001 closeout
  Discovery reports:
    - docs/evidence/m12/t001/discovery/legacy-archaeologist.md (acceptance line: PASS)
    - docs/evidence/m12/t001/discovery/requirements-skeptic.md  (acceptance line: PASS)
    - docs/evidence/m12/t001/discovery/design-red-team.md       (acceptance line: PASS)
  ADR: docs/adr/0018-generalized-competition-type.md
  Picked alternative: A | B | C (with one-line trade-off summary)
  Enum values present: kaggle | devpost | hackathon_devpost | ctf | generic
  PROJECT_STATE.md updated: YES
  Acceptance: PASS | FAIL — link to closing issue
  Risks / blockers: ...
  Next: M12-T002 (migration 0009 + policy resolver refactor)
```

## Related issues

- Closing issue for M12 — gets a comment linking ADR-0018 + the three
  discovery reports; transitions to `ai:ready` for T002 on PASS.
- Cross-link M11 placeholder issue (if filed) — note that the
  generalization includes `ctf` so M11 can reuse the schema.
- ADR-0006 — referenced, not superseded.

## Stop condition

Stop after 80 turns. If any agent's acceptance line is missing after
two attempts, halt and ask — do NOT patch the report by hand. If the
red team produces a "dropped capability" that breaks an M9 / M10
baseline (e.g. would force a Kaggle row to backfill non-trivially),
halt and ask — the ADR must preserve backwards compatibility.
