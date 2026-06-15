# Tasks — nemo

> Derived from issue #86 Table 2 (T1–T13). Full English tracking in `tracking.md`.

## Now
- Hold the **0.86** (`nemo-merge-soup`) entry through the **2026-06-15 23:59 UTC** deadline
  (quota 5/5 used today → locked). Manual: ensure the 0.86 soup is *selected* for private scoring.

## Next — top 4 post-competition tasks (picked from T5/v11, T6, T9, T12, GRPO/RL)
> The deadline is reached with 0/5 quota left, so these are post-competition; they are ordered by
> value-as-reusable-capability and by what unblocks the rest. Rationale + literature in `research.md`.
1. **T12 — local official metric + hard-val set** (✅ built this PR: `lib/official_metric.py` +
   `eval/hard_val_ids.json` + test). *Highest leverage:* it is the prerequisite to evaluate every other
   experiment without burning the 5/day quota; the audit's #1 missing infra.
2. **v11 / T5 — rejection-sampling (STaR/ReST-style) self-distillation.** Sample CoT (from v14, on-policy)
   → keep only ground-truth-correct → SFT. The untried distillation lever; needs a sample-kernel +
   train-kernel (multi-session, ~2–3 GPU runs — that is why it was deferred). Design in `research.md`.
3. **GRPO / RLVR (verifiable-reward RL).** The literature's strongest path for rule/puzzle reasoning
   (Logic-RL, LogicPuzzleRL, Tina). Heavy (online rollouts); run **after** v11 + a stable metric. Design
   in `research.md`.
4. **T9 — elevate `kca-<slug>.yaml` + on-the-fly metadata + flat layout + scheduling into KCA core**
   (#85). ~70% done (PR #106); promote `yaml_meta.py` into the `kca` CLI + multi-account user-pool.

> **Dropped: T6 (Unsloth seq8192)** — superseded; v14 already does seq8192 + the full recipe, so the
> marginal value is ~0.

## Validated this competition
- **Model-soup of comparable+complementary adapters** beats each member (v14+c1+b1 soup → 0.86). The
  reusable lever for the next competition: train N diverse same-base fine-tunes, then soup+SVD-rank-cap.

## Blocked
- None hard-blocking; constrained by deadline (06-15) and 5/day quota.

## Done
- T1 ctx4k (0.67), T2 ctx2k (0.42, negative-sample lesson), T4 v10 rule-CoT (0.59),
  T7 SVD merge (0.82, strong+weak route closed), T8 time-budget guard, T10 v14 replay (0.85),
  T11 v15 cryptarithm synth (0.84), T13 fix held-out eval truncation (512→7680 + time cap).
- Final sprint: b1 0.85, b2 0.84, c1 0.85 (verified solver-CoT), c2 0.83, **soup v14+c1+b1 = 0.86 (best)**.
- T12 local metric + hard-val: built this PR.
- All D1–D9 discussions confirmed (2026-06-12).

## Proposed GitHub issues
> Not created in this task; titles + acceptance below.
- "nemo: post-deadline archival — finalize submissions.md LB/CV + private-LB + final postmortem"
  (acceptance: submissions.md complete; private LB recorded if released; status → archived).
- "nemo: port official metric + min-logprob hard-val set (T12) for reuse" (acceptance: `eval/official_metric.py`
  + `eval/hard_val_ids.json` exist with a local unit test).
