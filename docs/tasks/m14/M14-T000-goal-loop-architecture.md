# M14-T000: `arch:` Goal-driven loop architecture + ADR-0020 (Discovery / Debate Gate)

## Milestone
M14: goal-driven Kaggle workflow.

## Tag
`arch:` — introduces a new architectural primitive (the goal-driven
Kaggle loop: goals, exploration batches, smart polling, concurrency
gate, stuck escalation). Triggers the **Discovery / Debate Gate** per
`docs/milestone-loop-protocol.md` §7.

## Goal
Write the canonical M14 design docs — `docs/adr/0020-goal-driven-kaggle-loop.md`
(decision record) and `docs/architecture/goal-driven-kaggle-loop.md`
(architecture + data-flow + state machine). Run the Discovery / Debate
Gate (`legacy-archaeologist` skippable for greenfield;
`requirements-skeptic` mandatory; `design-red-team` mandatory) and
attach all three transcripts under `docs/evidence/m14/T000/discovery/`.
Write the ten task specs `M14-T000-*.md` … `M14-T009-*.md` as the design
output.

No code, no migration, no CLI changes in this Loop Prompt. Design and
discovery only.

## Read first

1. `docs/milestones/README.md` §M14
2. `docs/milestone-loop-protocol.md` §7 (Discovery / Debate Gate)
3. `docs/architecture/discovery-debate-gate.md` (canonical acceptance lines)
4. `.claude/agents/requirements-skeptic.md`
5. `.claude/agents/legacy-archaeologist.md` (skip — greenfield; document it)
6. `.claude/agents/design-red-team.md`
7. `docs/milestones/m10/final-review.md` (single-push baseline; QUEUED-stall + 500 history)
8. `docs/adr/0006-configurable-approval-gates.md` (existing gate model)
9. `docs/adr/0010-model-routing.md` (route routing precedent)
10. `tools/kca/kg.py` (`cmd_push`, `cmd_submit`, `_watch_kernel_until_terminal`)
11. `src/worker/reviewer.py` (trigger ops + `_redact_tool_input`)
12. `supabase/migrations/0001_init.sql`, `0004_m4_competition_repo.sql`
    (live `competitions` / `submissions` / `experiment_runs` shapes)

## Scope

1. **Run the Discovery / Debate Gate.**
   - `legacy-archaeologist`: SKIP as greenfield (M14 builds on existing
     primitives; the one in-place revision — T005's poller cadence — is
     a source-controlled M10 primitive, not a `tools/legacy/` artefact).
     Write `docs/evidence/m14/T000/discovery/SKIP-NOTE.md` with the
     greenfield argument and the kkr.py-failure-mode-does-not-apply note.
   - `requirements-skeptic`: RAN. Save
     `docs/evidence/m14/T000/discovery/requirements-skeptic.md`. ≥5
     questions across ≥3 categories + non-empty `explicit_unknowns`.
   - `design-red-team`: RAN against a strawman ADR-0020. Save
     `docs/evidence/m14/T000/discovery/design-red-team.md`. ≥3
     alternatives, ≥1 dropped capability with file:line, 4 cost axes,
     actionable `open_disagreements`.
   - Verify all three canonical acceptance lines byte-for-byte against
     `docs/architecture/discovery-debate-gate.md`.

2. **Write `docs/adr/0020-goal-driven-kaggle-loop.md`** covering the
   eight decisions: goal.md schema; `goals` table + FKs; `experiment_runs`
   loop metadata (new `analysis_jsonb`, no `text→jsonb` cast); search-space
   YAML cross-product; exploration-batch lifecycle; smart-polling state
   machine; concurrency + daily-budget gate; stuck detector + escalation.

3. **Write `docs/architecture/goal-driven-kaggle-loop.md`** with ASCII
   data-flow, the four table layouts, the poller state machine diagram,
   the gate check order, the escalation payload schema, the reuse-vs-
   replace table, and the audit-grep sentinel inheritance.

4. **Write the ten task specs** `M14-T000-*.md` … `M14-T009-*.md` with
   scope, acceptance criteria, allowed/forbidden paths, closeout format.

5. **File the M14 proposal issue** (deferred if GitHub writes are not
   available in-session). Body links ADR-0020, the architecture doc, the
   three transcripts; labels `arch: type:feature ai:triage area:kaggle
   area:agent-sdk priority:P1`; collect the five human decisions from
   `docs/milestones/m14/loop-prompts.md` §"Human decisions needed before starting".

## Non-goals

- No migration SQL (T001), no Python under `tools/kca/` or `src/worker/`,
  no CLI registration, no `supabase/migrations/` change.
- Do not skip `requirements-skeptic` or `design-red-team`.

## Acceptance criteria

- `docs/adr/0020-goal-driven-kaggle-loop.md` exists; covers all eight
  decisions; cross-links the architecture doc.
- `docs/architecture/goal-driven-kaggle-loop.md` exists; ASCII data-flow
  + 4 table layouts + state-machine diagram + escalation schema render.
- `docs/evidence/m14/T000/discovery/{SKIP-NOTE,requirements-skeptic,design-red-team}.md`
  exist.
- All three canonical acceptance lines from
  `docs/architecture/discovery-debate-gate.md` appear verbatim in the
  corresponding transcripts.
- The ten task specs `docs/tasks/m14/M14-T00{0..9}-*.md` exist with scope,
  acceptance criteria, allowed/forbidden paths, closeout format.
- `ruff check .` / `ruff format --check .` clean (no Python changed).
- No source code (`src/`, `tools/`, `tests/`, `ui/`,
  `supabase/migrations/`) modified.

## Allowed / forbidden paths

- ALLOWED (write): `docs/adr/0020-*.md`, `docs/architecture/goal-driven-kaggle-loop.md`,
  `docs/evidence/m14/T000/discovery/*`, `docs/tasks/m14/M14-T00*.md`.
- FORBIDDEN (write): `src/**`, `tools/**`, `tests/**`, `ui/**`,
  `supabase/migrations/**`, any non-M14 doc.

## Permissions

- `git add` deferred to milestone closeout (T009); no commit/push/PR
  mid-milestone.
- `gh issue create` for the M14 proposal issue — ALLOWED if available;
  deferred otherwise (recorded as a follow-up).
- No real Kaggle / Anthropic / OpenAI calls.

## Closeout format

```
M14-T000 closeout
  ADR: docs/adr/0020-goal-driven-kaggle-loop.md (written; 8 decisions)
  Architecture: docs/architecture/goal-driven-kaggle-loop.md (written; data-flow + 4 tables + state machine)
  Discovery / Debate Gate:
    legacy-archaeologist: SKIP (greenfield; see SKIP-NOTE.md)
    requirements-skeptic: RAN — <n> questions across <c> categories; explicit_unknowns: <list>
    design-red-team: RAN — <n> alternatives; <m> dropped capabilities; open_disagreements: <list>
  Canonical acceptance lines: 3/3 verified byte-for-byte
  Task specs: docs/tasks/m14/M14-T000..T009 (10 written)
  Proposal issue: <url | deferred>
  Acceptance: PASS — design + gate complete; no code changed
  Next: M14-T001 (migration 0011 + DB helpers)
```

## Related issues

- M14 proposal issue (filed in this Loop Prompt) — decision record.
- Issues #51 #52 #53 #54 #55 (per-bullet tracking); #7 #8 #62 #63 folded
  into the plan; #21 #60 cross-referenced + deferred.

## Stop condition

Stop after 80 turns. HALT and ask if:
- Any of the three canonical acceptance lines cannot be produced
  byte-for-byte (the `.claude/agents/` definitions are source of truth).
- The strawman ADR lands a load-bearing schema decision the red-team
  flags without evidence — add evidence or split into a follow-up ADR.
- A human-decision input (`docs/milestones/m14/loop-prompts.md` §"Human decisions")
  blocks a load-bearing ADR decision — surface it in the closeout and
  leave the proposal issue at `decision:needed`.
