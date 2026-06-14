# SKIP-NOTE — legacy-archaeologist (M14-T000)

Date: 2026-06-10
Task: `M14-T000` — goal-driven Kaggle loop architecture + ADR-0020.
Gate stage: 1 of 3 (legacy-archaeologist).
Decision: **SKIPPED** as greenfield, per
`docs/architecture/discovery-debate-gate.md` §"When the gate fires"
(skip allowed for greenfield `arch:` tasks with no legacy code in
scope) and the explicit allowance in the M14 Loop Prompt 0 read-list
(`docs/milestones/m14/loop-prompts.md:136`, `:154-156`).

## Greenfield argument

M14's goal-driven loop is a **composition layer** built on top of
existing M10 primitives that are themselves not being migrated or
rewritten. There is no legacy artefact to mine:

- There is no prior `goals` table. `git grep -n "create table goals\|goal_id"`
  on the worktree base returns no matches in `supabase/migrations/`. The
  closest existing column is `agent_sessions.goal text`
  (`supabase/migrations/0001_init.sql:50`), which is a free-text session
  note, not a competition target record. M14's `goals` table sits
  alongside it, not as a replacement.
- There is no prior `kca goal` or `kca explore` CLI verb. The closest
  precedents are `kca competition register` (`tools/kca/competition.py`)
  and `kca run` (`tools/kca/run.py`). Neither is being migrated; the new
  verbs are additive top-level commands following the same four-layer CLI
  shape.
- There is no prior exploration-batch / search-space mechanism. The
  closest is the single-experiment local-train scripts
  (`scripts/m10_t002_local_train.py`, `scripts/m10_t005_local_train.py`),
  which T003 *templates from* but does not replace — the seed
  `baseline.py` stays the seed.
- The smart-polling work (T005) **revises an existing function**
  (`tools/kca/kg.py::_watch_kernel_until_terminal`,
  `tools/kca/kg.py:280-363`), but that is an M10 platform primitive on
  `main`, not a *legacy* artefact in the `tools/legacy/` sense the gate
  was created for. It is in-scope, source-controlled, and covered by the
  `requirements-skeptic` + `design-red-team` transcripts below, which
  explicitly enumerate its current behaviour (fixed 60 s cadence,
  `kernels output`-size terminal detection) so the revision cannot drop
  it silently.

What the new loop REUSES (versus what it migrates):

- `tools/kca/kg.py::cmd_push` / `cmd_submit` — the approval-gate +
  side-effect envelope is reused; T004 *adds* a credentials pre-check and
  concurrency/daily-budget gating in front of the existing path. Not a
  rewrite of the push mechanics.
- `tools/kca/kg.py::_watch_kernel_until_terminal` — the watcher entry
  point is reused; T005 replaces the cadence policy inside it but keeps
  the `kernels output` terminal-detection fallback discovered in M10-T004.
- `src/worker/reviewer.py` — the existing reviewer gate
  (`DEFAULT_TRIGGER_OPS`, `src/worker/reviewer.py:20-34`) is extended with
  a new `kaggle.exploration_stuck` decision_type, not replaced.
- `services/decision_api/app.py` + `ui/src/pages/ApprovalInbox.tsx` — the
  Approval Inbox surface is reused for the new escalation decision_type;
  T007 adds a row shape, not a new surface.
- `tools/kca/research.py` + `.claude/skills/research-brief/` — T006
  extends the existing research-brief untrusted-data filter; no rewrite.

## The kkr.py failure mode does not apply here

The Discovery / Debate Gate's stated origin
(`docs/architecture/discovery-debate-gate.md` §"What this is", citing
`docs/meeting-notes/2026-05-24-r3.md` §6) is the `tools/legacy/kkr.py`
migration that dropped multi-Kaggle-account / owner / env semantics
because no agent role surfaced them. That failure mode fires when a
*legacy artefact is migrated*. M14 builds a new loop on top of stable,
source-controlled primitives; the one in-place revision (T005's cadence
policy) is small, well-bounded, and its prior behaviour is enumerated in
the skeptic + red-team transcripts.

The single-account-only scope is itself a load-bearing carry-over of the
kkr.py lesson: M14 deliberately ships only the **single-account**
concurrency primitive (T004) and defers the multi-account quota pool to
issue #21 / M15+ (`docs/milestones/m14/loop-prompts.md:45-47`, `:84-87`), precisely
so the multi-account semantics are designed deliberately later rather
than half-encoded now.

## What this skip does NOT excuse

- The `requirements-skeptic` and `design-red-team` agents both ran
  (mandatory under M9.4, never skippable). Their transcripts live
  alongside this note at
  `docs/evidence/m14/T000/discovery/requirements-skeptic.md` and
  `docs/evidence/m14/T000/discovery/design-red-team.md`.
- The M10-T007 audit-grep sentinel ("0 lines reach `kaggle kernels push`
  / `kaggle competitions submit` from any non-approved process") still
  applies to every M14 test path. T008 is the *only* task with a real
  Kaggle write, and only under explicit per-batch human approval.
- If a future M14 sub-task ends up touching a genuine legacy artefact
  (e.g. `tools/legacy/py2nb.py`'s kernelspec emitter, or `kkr.py`
  itself), the agent MUST re-trigger the gate with `legacy-archaeologist`
  RUNNING — this skip is per-task, not per-milestone.

## Confirmation marker

This skip is acceptable only IF the M14 proposal issue carries a
`decision:confirmed` comment naming the skip (mirrors the M13-T000
posture). T000's closeout surfaces this requirement; T001 MUST NOT start
until the marker is in place. Note: at the time of writing, GitHub issue
creation in this worktree session is deferred — the closeout records the
proposal-issue action as a follow-up, not as completed.
