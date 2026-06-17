# M15-T007: live autonomous submit validation — record ≥1 real LB score

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Run the goal-driven loop on a real Kaggle competition so it pushes → **submits**
→ records **≥1 real leaderboard score**, closing the M14-T008 "0 new LB scores"
deviation. The submit runs **screened-autonomous** under ADR-0021; scenario-4 /
over-budget / ambiguous-rules stay human-gated. Capture an auditable run record.

Depends on **M15-T001 (real limits) and M15-T002 (submit step) closeouts = PASS**.

## Read first
1. M15-T002 closeout (the submit step being exercised live).
2. M15-T001 closeout (refresh-rules so live limits are real).
3. `docs/adr/0021-kca-autonomy-model.md` (autonomy screen + audit contract +
   scenario-4 human gate).
4. `docs/evidence/m14/T008/live-run.md` (the deviation this closes — same shape
   of evidence record).
5. `CLAUDE.md` §"KCA autonomous submission strategy" (the 4 scenarios + the
   ~2h-before-rollover timing + closing threshold).
6. `tools/kca/kg.py` (`cmd_push`, submit step, `cmd_score`, `_check_budget_gates`).

## Scope
1. Run the loop on a real competition (default `tpu-getting-started`, re-using
   the M10/M14 surface, unless T000/T002 picked a different competition): goal
   set → explore/select → `kca kaggle push` → terminal → **submit** → score.
2. The submit is **screened-autonomous**: when
   `kca-<slug>.yaml:autonomy.enabled` is true and `autonomy.screen` passes, KCA
   records the intended-submission summary (file / experiment id / expected
   score / reason) to `.agent/kca/audit.jsonl` and submits without per-action
   approval. Scenario-4 (multiple candidates, closing soon) / over-budget /
   ambiguous-rules → human-gated.
3. Record **≥1 real `submissions.public_lb_score`** written via the submit →
   score path.
4. Capture an auditable run record under `docs/evidence/m15/T007/` (mirror the
   M14-T008 `live-run.md` shape: goal, pushes, submits, scores, audit-row refs,
   findings).

## Non-goals
- No code changes — this exercises T001/T002's code. Any bug found is fixed back
  in the owning task, not here.
- No leaderboard chasing beyond proving the submit → score loop records a real
  score; not a modelling-improvement task.

## Acceptance criteria
- The live run pushes → submits → records **≥1 real LB score** (the M14-T008
  deviation is closed).
- The submit was screened-autonomous: an intended-submission summary row exists
  in `.agent/kca/audit.jsonl` (file / experiment id / expected score / reason).
- `kca kaggle score` wrote a non-NULL `submissions.public_lb_score` for the
  submitted run.
- The daily-submission budget gate counted the submit (per T002).
- `docs/evidence/m15/T007/live-run.md` exists with the run record.

## Allowed / forbidden paths
- ALLOWED: `docs/evidence/m15/T007/**`, `experiments/<comp>/**` (generated run
  artefacts), `kca-<slug>.yaml` (autonomy config for the target competition).
- FORBIDDEN: `tools/kca/**` code edits (fix bugs in the owning task),
  `supabase/migrations/**`.

## Permissions
- **REAL Kaggle push + submit** — needs `dangerouslyDisableSandbox=true`
  (network out to `kaggle.com`) and `KAGGLE_USERNAME` / `KAGGLE_KEY` present.
- Submit is screened-autonomous under ADR-0021 (audit row, no per-action ask)
  when autonomy is enabled + screen passes; human-gated for scenario-4 /
  over-budget / ambiguous rules.
- No paid LLM required for the loop mechanics.

## Closeout format
```
M15-T007 closeout
  Competition: <slug>; goal: <target>
  Push → terminal → submit → score: completed; submit screened-autonomous (audit row in .agent/kca/audit.jsonl)
  Real LB: submissions.id=<...> public_lb_score=<score> (≥1 real score recorded)
  Budget gate: submit counted
  Evidence: docs/evidence/m15/T007/live-run.md
  Acceptance: PASS (M14-T008 deviation closed)
  Next: M15-T008 (regression + exit criteria + final review)
```

## Related issues
- #77 (the submit step this validates end-to-end on real LB signal).

## Stop condition
Stop after 80 turns. HALT and ask if:
- A real Kaggle push/submit returns an error (rate limit, bad metadata, rules
  violation) — fix the path in the owning task, re-screen, do NOT silently retry.
- The autonomy screen lands in scenario-4 (multiple candidates beat best,
  closing soon) or over-budget / ambiguous-rules — hand back to the human per
  ADR-0021.
- Credentials or `.env*` are printed in any log / audit row / evidence doc —
  stop and rotate the credential.
