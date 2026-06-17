# M15-T002: explicit submit step between push-terminal and `kca kaggle score` (issue #77)

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Add the explicit competition **submit** between a kernel reaching terminal and
`kca kaggle score`, so the goal loop advances on real leaderboard signal. Wire
the submit through the ADR-0021 autonomy screen and make the ADR-0020 §7
daily-budget gate count the *submit*, not just the push. This is the M15
headline task — it closes the M14-T008 "0 new LB scores" deviation.

Assumes **M15-T000 (design) and M15-T001 (real limits) closeouts are PASS**.

## Read first
1. M15-T000 closeout (ADR-0020 addendum — the submit-mechanism decision).
2. M15-T001 closeout (refresh-rules port).
3. Issue #77 (acceptance criteria — pin to the issue body).
4. `tools/kca/kg.py` — `cmd_push` (~433), `_watch_kernel_until_terminal` (~697),
   `cmd_score` (~1317), `_check_budget_gates` (~195).
5. `docs/adr/0021-kca-autonomy-model.md` (autonomy screen + audit contract).
6. `tools/kca/agent/audit.py` + the KCA audit-log path `.agent/kca/audit.jsonl`.
   (Note: `CLAUDE.md` still names this `.agent/audit.jsonl`; the code path is
   `.agent/kca/audit.jsonl` per PR #120 — follow the code, flag the doc drift.)

## Scope
1. **Submit step** between push-terminal and score, per the T000-chosen
   mechanism (output-CSV `kaggle competitions submit` or kernel "Submit to
   Competition"): after `_watch_kernel_until_terminal` reports terminal, submit
   the kernel's output; record the `external_submission_id` so `cmd_score` can
   match the resulting LB row and write `submissions.public_lb_score`.
2. **Autonomy screen** (ADR-0021): the submit is autonomous when
   `kca-<slug>.yaml:autonomy.enabled` is true and `autonomy.screen` passes —
   record the intended-submission summary (file / experiment id / expected
   score / reason) to `.agent/kca/audit.jsonl` instead of asking; else surface
   the summary and ask. Scenario-4 / over-budget / ambiguous-rules stay
   human-gated.
3. **Budget gate**: extend `_check_budget_gates` so the daily-submission count
   accounts for the submit (per ADR-0020 §7), not only the push.

## Non-goals
- No refresh-rules changes (T001), no schema changes, no autonomy-model redesign
  (consume ADR-0021 as written).
- No real Kaggle submit in this Loop Prompt — the e2e test mocks the submit. The
  live exercise is T007.

## Acceptance criteria
_Pinned to issue #77:_
- The loop performs an explicit submit between push-terminal and
  `kca kaggle score` (output-CSV `kaggle competitions submit`, or the kernel
  "Submit to Competition" action — per T000).
- After a successful kernel run, `kca kaggle score` finds the resulting LB row
  and writes `submissions.public_lb_score`.
- The daily-submission budget gate (ADR-0020 §7) accounts for the submit (not
  just the push).
- An e2e/dry test covers push → submit → score with the submit step mocked.
- (M15) the submit honours the ADR-0021 autonomy screen: autonomous + audit row
  when enabled & screen-pass; asks otherwise.
- `ruff check .` / `ruff format --check .` clean; no pytest regressions.

## Allowed / forbidden paths
- ALLOWED: `tools/kca/kg.py` (submit step + `_check_budget_gates`),
  `tools/kca/agent/audit.py` (if the audit summary needs a helper),
  `tests/test_m15_*.py` (new e2e/dry tests).
- FORBIDDEN: `supabase/migrations/**`, `tools/kca/competition.py`,
  `docs/adr/0021-*` (consume, don't edit).

## Permissions
- No real Kaggle / LLM in this task (submit mocked). LOCAL_WRITE (Supabase)
  ALLOWED for the `submissions` writes in the e2e fixture path.

## Closeout format
```
M15-T002 closeout
  Submit step: <output-csv|kernel-submit> wired between terminal and score
  cmd_score: matches resulting LB row → submissions.public_lb_score (mocked e2e)
  Autonomy: ADR-0021 screen → autonomous+audit when enabled; asks otherwise
  Budget gate: _check_budget_gates counts the submit
  e2e/dry test: push → submit → score (submit mocked) green
  pytest / ruff: <X> passed; clean
  Acceptance: PASS (live LB score deferred to T007)
  Next: M15-T003 (submission_format schema)
```

## Related issues
- #77 (goal loop needs explicit submit step).

## Stop condition
Stop after 60 turns. HALT and ask if:
- Issue #77's acceptance criteria conflict with the T000 addendum's
  submit-mechanism choice — pin the conflict and ask before diverging.
- The chosen mechanism needs a code-competition-only API path the target
  competition does not support — surface it; this may push the live validation
  (T007) to a different competition.
