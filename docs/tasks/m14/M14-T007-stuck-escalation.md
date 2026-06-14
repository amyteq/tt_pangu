# M14-T007: Stuck detector + human escalation via Approval Inbox (issue #55)

## Milestone
M14: goal-driven Kaggle workflow.

## Goal
Implement the stuck detector and the human-escalation surface of
ADR-0020 §8. The detector fires when N consecutive submissions show no
monotone LB improvement AND idea-sourcing returned 0 fresh candidates.
On stuck: write a redacted escalation doc, insert a
`kaggle.exploration_stuck` `human_decisions` row, and surface it in the
Approval Inbox. A human response resumes the loop with a new seed.

Assumes **M14-T000 / T002 / T006 closeouts are PASS**.

## Read first
1. M14-T000 / T002 / T006 closeouts.
2. `docs/adr/0020-goal-driven-kaggle-loop.md` §8 (heuristic + NULL-score rule + payload + redaction + resume).
3. `docs/architecture/goal-driven-kaggle-loop.md` (escalation payload schema).
4. Issue #55 (acceptance criteria).
5. `src/worker/reviewer.py` (`DEFAULT_TRIGGER_OPS` `:20-34`; `_redact_tool_input` `:96-118`).
6. `services/decision_api/app.py` (Approval Inbox surface).
7. `ui/src/pages/ApprovalInbox.tsx`.
8. `docs/tasks/m9/M9-T003` / `M10-T003` (kaggle_submit / kernel_push escalation precedents).
9. Issue #60 (`approved_by_user_id` FK — write the column if present, ignore otherwise).

## Scope
1. **Stuck detector.** Fires when N (= `goal.stuck_threshold`, default 3)
   consecutive **scored** submissions show no monotone LB improvement AND
   `kca explore propose-next` returned 0 fresh candidates. **NULL-score
   rule:** a submission with NULL `public_lb_score` is "no result" — does
   not advance and does not reset the non-improving counter.
2. **Escalation artefact.** On stuck, write `docs/escalations/<comp>-<ts>.md`
   with: goal vs current; table of tried strategies (axes + holdout + LB
   per screened/pushed run); sources consulted (T006 `source_url` +
   `trust_label`); ruled-out hypotheses; concrete questions.
3. **Decision row.** Insert a `human_decisions` row with
   `decision_type=kaggle.exploration_stuck` and the structured payload;
   extend the reviewer's `DEFAULT_TRIGGER_OPS`. Write
   `approved_by_user_id` if the column exists (#60), ignore if not.
4. **Redaction.** The payload + escalation doc pass through a
   `_redact_tool_input`-style filter — no DSN / credential / flag is
   rendered into the committed doc or the audit row.
5. **Resume.** A human response (UI form or `kca decisions approve
   --notes "<direction>"`) becomes the new exploration seed; the loop
   reads notes as a structured option or free-text direction and resumes
   with a fresh batch; the resolving `human_decisions.id` is recorded as
   the new run's `analysis_jsonb.escalation_id`.
6. **Telemetry.** Count escalations + time-to-resolution per competition.

## Non-goals
- No real Kaggle push (T008).
- No `approved_by_user_id` FK hardening (#60 / separate audit task).
- No new Approval Inbox surface — reuse the existing one.

## Acceptance criteria
- The detector fires after exactly 3 non-improving SCORED submissions
  with 0 fresh candidates (fixture-driven); a NULL-score submission
  neither advances nor resets the counter (assert both).
- `docs/escalations/<comp>-<ts>.md` is written with all payload sections;
  a crafted DSN/credential in the input is redacted in the doc AND the
  `human_decisions` row (assert via a no-secret sentinel grep).
- A `human_decisions` row with `decision_type=kaggle.exploration_stuck`
  is inserted and visible in the Approval Inbox (`GET` surface).
- `kca decisions approve --notes "<direction>"` resolves the row and the
  resolving id lands on the resumed run's `analysis_jsonb.escalation_id`.
- Escalation count + time-to-resolution telemetry recorded per comp.
- Audit-grep: 0 lines reach `kaggle kernels push` / `kaggle competitions submit`.
- `ruff check .` / `ruff format --check .` clean; no pytest regressions
  (incl. `services/decision_api/tests`).

## Allowed / forbidden paths
- ALLOWED: `src/worker/reviewer.py` (trigger op + redaction reuse),
  `services/decision_api/app.py` (new decision_type handling),
  `ui/src/pages/ApprovalInbox.tsx`, `tools/kca/decisions.py` (resume notes),
  `tools/kca/explore.py` (detector hook), `docs/escalations/**` (generated),
  `tests/test_m14_*`.
- FORBIDDEN: `supabase/migrations/**` (the `approved_by_user_id` FK is
  #60, separate); `tools/kca/kg.py` push mechanics.

## Permissions
- LOCAL_WRITE (Supabase) — ALLOWED.
- No real Kaggle / LLM (detector uses recorded submissions + T006 output).
- `git add` deferred to T009.

## Closeout format
```
M14-T007 closeout
  Detector: fires at stuck_threshold non-improving SCORED submissions + 0 fresh candidates
  NULL-score rule: NULL public_lb_score neither advances nor resets (verified)
  Escalation doc: docs/escalations/<comp>-<ts>.md written; secret-redacted (verified)
  Decision row: kaggle.exploration_stuck inserted; visible in Approval Inbox
  Resume: approve --notes -> new seed; escalation_id on resumed run
  Telemetry: escalation count + time-to-resolution per comp
  Audit-grep: 0 real Kaggle lines
  pytest / ruff: <X> passed; clean
  Acceptance: PASS
  Next: M14-T008 (live end-to-end)
```

## Related issues
- #55 (human-in-the-loop escalation). Cross-ref #60 (FK hardening — deferred).

## Stop condition
Stop after 60 turns. HALT and ask if:
- The escalation doc cannot be guaranteed secret-free — do NOT write it;
  surface and fix the redaction first (milestone stop criterion:
  credential leak in an escalation doc).
- The Approval Inbox surface cannot render the new decision_type without
  a UI schema change beyond scope — pin the minimal change and confirm.
