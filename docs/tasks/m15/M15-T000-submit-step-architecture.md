# M15-T000: explicit-submit-step architecture — ADR-0020 addendum (`arch:`)

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Design the explicit **submit step** that sits between push-terminal and
`kca kaggle score`, and decide how it integrates with the ADR-0021 autonomy
screen and the ADR-0020 §7 daily-budget gate. Output an **addendum to
ADR-0020** (not a new ADR — this builds on the existing goal-loop design) plus
the eight downstream M15 task specs. No code, no migration, no CLI changes in
this Loop Prompt — design only.

This is the architecture phase; it gates every other M15 task.

## Read first
1. `docs/adr/0020-goal-driven-kaggle-loop.md` (whole doc; esp. §7 budget gate +
   "Known gaps / follow-ups" which names #77/#78).
2. `docs/adr/0021-kca-autonomy-model.md` (autonomy screen, audit-log contract).
3. Issue #77 (the headline gap — pin the acceptance criteria to the issue body).
4. `docs/evidence/m14/T008/live-run.md` ("Scores" + Findings #4 — why push ≠ submit).
5. `tools/kca/kg.py` — `cmd_push` (~433), `_watch_kernel_until_terminal` (~697),
   `cmd_score` (~1317), `_check_budget_gates` (~195).
6. `docs/architecture/discovery-debate-gate.md` + the three gate agents
   (`.claude/agents/requirements-skeptic.md`, `legacy-archaeologist.md`,
   `design-red-team.md`).
7. `docs/milestone-loop-protocol.md` §7 (Discovery / Debate Gate is MANDATORY
   for `arch:` tasks).

## Scope
1. **ADR-0020 addendum** (append a dated "M15 addendum — explicit submit step"
   section to `docs/adr/0020-goal-driven-kaggle-loop.md`, or a sibling
   `docs/adr/0020a-explicit-submit-step.md` if the addendum is large — decide
   and note which) covering:
   - **Submit mechanism decision**: submit-the-kernel-output-CSV
     (`kaggle competitions submit -f <output.csv>`) vs the kernel
     "Submit to Competition" action — pick one, with the trade-offs (output-CSV
     retrieval, code-competition constraints, idempotency / double-submit
     guards).
   - **Loop placement**: where the submit fires in
     push → terminal → **submit** → score, and how `cmd_score` then matches the
     resulting LB row.
   - **Autonomy integration** (ADR-0021): the submit is screened-autonomous when
     `kca-<slug>.yaml:autonomy.enabled` is true and `autonomy.screen` passes —
     KCA records the intended-submission summary (file / experiment id / expected
     score / reason) to the KCA audit log (`.agent/kca/audit.jsonl`) instead of
     asking; else it asks. Scenario-4 / over-budget / ambiguous-rules stay
     human-gated.
   - **Budget-gate accounting**: `_check_budget_gates` must count the *submit*
     against `max_daily_submissions`, not (only) the push.
2. **The eight downstream task specs** `docs/tasks/m15/M15-T001-*.md` …
   `M15-T008-*.md` as the design output (this file is T000's own spec).

## Non-goals
- No implementation of the submit step (T002), no migrations (T004), no CLI
  changes — design + task-spec authoring only.
- Not re-opening the cross-account quota / multi-account design (#21/#85) or
  cheaper-GPU (#83) — those are M16, `decision:needed`.

## Acceptance criteria
- The ADR-0020 addendum exists and records the submit-mechanism decision
  (output-CSV vs kernel-submit) with rationale.
- The addendum specifies the loop placement push → submit → score and the
  autonomy/budget integration (ADR-0021 screen + `_check_budget_gates` counts
  the submit).
- All eight downstream task specs (T001–T008) exist under `docs/tasks/m15/`,
  each with the canonical sections (Milestone, Goal, Read first, Scope,
  Non-goals, Acceptance criteria, Allowed / forbidden paths, Permissions,
  Closeout format, Related issues, Stop condition).
- Discovery / Debate Gate run per protocol §7; transcripts under
  `docs/evidence/m15/T000/discovery/` (the `legacy-archaeologist` skip is
  allowed with an explicit greenfield note — M15 builds on existing primitives).
- No code / migration / CLI diff in this Loop Prompt (`git status` shows only
  `docs/` additions).

## Allowed / forbidden paths
- ALLOWED: `docs/adr/0020-goal-driven-kaggle-loop.md` (addendum) or
  `docs/adr/0020a-explicit-submit-step.md`, `docs/tasks/m15/**`,
  `docs/evidence/m15/T000/**`.
- FORBIDDEN: any `tools/kca/**`, `supabase/migrations/**`, `src/**` change —
  design only.

## Permissions
- No real Kaggle / LLM calls. No DB writes. Read-only exploration of the
  codebase; doc writes only.

## Closeout format
```
M15-T000 closeout
  ADR-0020 addendum: submit mechanism = <output-csv|kernel-submit>; rationale recorded
  Loop placement: push → submit → score; cmd_score match path documented
  Autonomy: ADR-0021 screen wired into submit; audit → .agent/kca/audit.jsonl
  Budget gate: _check_budget_gates counts the submit (design)
  Task specs: docs/tasks/m15/M15-T001..T008 written (8 specs, canonical sections)
  Discovery/Debate Gate: transcripts under docs/evidence/m15/T000/discovery/ (legacy-archaeologist skipped — greenfield note)
  Acceptance: PASS
  Next: M15-T001 (refresh-rules port — so live runs get real limits)
```

## Related issues
- #77 (explicit submit step — the design target).
- #78 (refresh-rules port — sequenced first downstream so live runs get limits).

## Stop condition
Stop after 80 turns. HALT and ask if:
- The Discovery / Debate Gate flags a load-bearing requirement the addendum
  does not address (fix the addendum; do not skip).
- The submit-mechanism choice depends on a competition-rules fact not knowable
  offline (e.g. whether the target competition is code-only) — surface it and
  ask before committing the decision.
