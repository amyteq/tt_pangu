# Tasks — nemo

> Derived from issue #86 Table 2 (T1–T13). Full English tracking in `tracking.md`.

## Now
- Hold the **0.85** (`nemo-replay-v14`) entry through the **2026-06-15 23:59 UTC** deadline.

## Next
- (Optional, low-cost, user-decides) T11 variant: **half-dose cryptarithm-only synth** (~800 ex / ~8%)
  to cut dilution while keeping the cryptarithm signal — expected ≤0.85.

## Backlog (post-competition)
- T9: per-competition YAML + user-pool tooling (issue #85; deferred post-comp by D6).
- T12: localize official `score()` / `extract_final_answer()` / `verify()` + min-logprob hard-val set.
- T5: v11 rejection-sampling self-distillation (D2 approved, never run — out of GPU/time budget).
- T6: v12 Unsloth ~1 epoch / seq8192 (superseded by v14 replay success).

## Blocked
- None hard-blocking; constrained by deadline (06-15) and 5/day quota.

## Done
- T1 ctx4k (0.67), T2 ctx2k (0.42, negative-sample lesson), T4 v10 rule-CoT (0.59),
  T7 SVD merge (0.82, route closed), T8 time-budget guard, T10 **v14 replay (0.85, best)**,
  T11 v15 cryptarithm synth (0.84), T13 fix held-out eval truncation (512→7680 + time cap).
- All D1–D9 discussions confirmed (2026-06-12).

## Proposed GitHub issues
> Not created in this task; titles + acceptance below.
- "nemo: post-deadline archival — finalize submissions.md LB/CV + private-LB + final postmortem"
  (acceptance: submissions.md complete; private LB recorded if released; status → archived).
- "nemo: port official metric + min-logprob hard-val set (T12) for reuse" (acceptance: `eval/official_metric.py`
  + `eval/hard_val_ids.json` exist with a local unit test).
