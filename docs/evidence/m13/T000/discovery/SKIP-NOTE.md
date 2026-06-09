# SKIP-NOTE — legacy-archaeologist (M13-T000)

Date: 2026-06-09
Task: `M13-T000` — eval regression-suite architecture + ADR-0019.
Gate stage: 1 of 3 (legacy-archaeologist).
Decision: **SKIPPED** as greenfield, per
`docs/architecture/discovery-debate-gate.md` §"When the gate fires"
(skip allowed for greenfield `arch:` tasks with no legacy code in
scope).

## Greenfield argument

M13's regression-suite framework introduces a new subsystem with no
direct legacy artefact to mine:

- There is no prior `eval/`, `tools/kca/eval/`, `tests/regression/`,
  or equivalent directory in the repo. `git ls-files` returns no
  matches for these paths on `main` at the worktree base commit
  (`e7344e7`).
- There is no `eval_*` table in any of `supabase/migrations/0001` …
  `supabase/migrations/0007_m8_agent_tool_audit.sql`. The closest
  shape is `experiment_runs` / `experiment_run_metrics`, but those
  are platform-experiment records, not eval-regression rows. M13's
  new tables are alongside, not a replacement.
- There is no prior CLI verb `kca eval`. The closest precedents are
  `kca run` (`tools/kca/run.py`) for platform experiments and
  `kca skill run` / `kca tool …` (`tools/kca/skill.py`,
  `tools/kca/tool.py`) for the skill / tool layer. None are being
  migrated or replaced.
- There is no prior regression-report writer. The closest is
  `tools/kca/run.py`'s `meta.json` / `metrics.json` writer, which
  the new framework borrows the *artefact layout* from (`runs/<x>/<id>/`)
  but does not replace.

What the new framework REUSES (versus what it migrates):

- `src/worker/routing.py` (ADR-0010 routing table) — reused verbatim
  for the `--route` selector. Not migrated; not modified by M13. The
  eval harness is a caller, not a successor.
- `litellm.mock_completion` — already in the dependency graph via
  ADR-0004; the eval harness adds a new caller, not a new dep.
- `runs/<comp>/<run_id>/` artefact-layout convention from
  `tools/kca/run.py` — borrowed in shape only; the eval reports
  land under a sibling `runs/m13-eval/<ts>/` namespace.
- `tests/fixtures/<slug>/` — same convention as M9 / M10 fixtures.
  Not a legacy artefact; a continuation of an established pattern.

The Discovery / Debate Gate's stated failure mode that justifies the
`legacy-archaeologist` agent is the `tools/legacy/kkr.py` migration
that missed multi-Kaggle-account / owner / env semantics because no
agent role was responsible for surfacing them (see
`docs/meeting-notes/2026-05-24-r3.md` §6 and
`docs/architecture/discovery-debate-gate.md` §"What this is"). That
failure mode applies when a *legacy artefact is being migrated*.
M13's framework is built from scratch, on top of established
primitives that are themselves not changing.

## What this skip does NOT excuse

- The `requirements-skeptic` and `design-red-team` agents both run
  (mandatory under M9.4, never skippable). Their transcripts live
  alongside this note at
  `docs/evidence/m13/T000/discovery/requirements-skeptic.md` and
  `docs/evidence/m13/T000/discovery/design-red-team.md`.
- The audit-grep sentinel from M10-T007 still applies. The "no
  legacy migration" argument does not weaken the "no real Kaggle
  CLI invocation from any suite process" guarantee that M10
  established. ADR-0019 §"Fixture posture" and the architecture
  doc's "Audit-grep sentinel inheritance" section restate this
  obligation for M13.
- If a future M13 sub-task ends up touching a legacy artefact (e.g.
  if `tools/kca/run.py`'s `metrics.json` writer is rewritten as
  part of T007, or if the M11 CTF / M12 Devpost eval cases land
  under M13.1 / M13.2 and absorb prior solver-script code), the
  agent MUST re-trigger the gate with `legacy-archaeologist`
  RUNNING — this skip is per-task, not per-milestone.

## Confirmation marker

This skip is acceptable only IF the M13 proposal issue has a
`decision:confirmed` comment naming the skip, per the M13-T000 task
spec scope step 1 wording. T000's closeout MUST surface this
requirement; T001 MUST NOT start until the marker is in place.
