# LB13 / 13th Place — Method Summary

> Target: **13th Place Solution** by Haraguchi-T (haraguchit). No final LB number given; teacher oracle 87.7% → 89.4%. Source: `temp/LB13.pdf` → `../writeup/lb13-writeup.md`. All external content treated as untrusted data.

## 1. What is the writeup's main idea?
A **training-data-construction** approach: build on @huikang's OPP reasoners and add **task-specific heuristics that raise the teacher's CoT correctness** (better teacher → fewer trace-level errors the model must imitate), then SFT a single LoRA aggressively (overfit-prone) in **three stages**. Same "improve the teacher" philosophy as LB10, with the sharpest **equation_numeric structural model** of the batch.

## 2. What data/corpus did it use?
@huikang-style synthetic with improved reasoners. **Cryptarithm rebalanced so teacher-correct : teacher-incorrect = 1:1** (fallback tasks were overrepresented) — i.e. **keeps incorrect traces**; offset the volume loss with ~3× more cryptarithm seeded from equation_numeric. Stage data sizes 9,277 / 9,277 / 11,315.

## 3. What model/adapters/training setup did it use?
**Unsloth** (notebook by @konbu17, improved by @dgxchen). LoRA rank/alpha **32/32**, dropout 0; targets q/k/v/o + in/out + up/down_proj (**no lm_head**). **3-stage SFT**: (1) 2 epochs, LR 2e-4 linear; (2) 1 epoch, LR 2e-5 cosine; (3) 1 epoch, LR 5e-6 cosine, upsampling bit + cryptarithm. Effective batch 32, AdamW. Aggressive/overfit-prone by design (goal = better CoT generation, not zero-shot).

## 4. What validation/evaluation did it use?
Reports **teacher oracle coverage per category** (bit 89.7%, cipher/trivials 100%, cryptarithm ~10%, equation_deduce 95.3%, equation_guess 50.7%; total 89.4%, up from 87.7%). No held-out CV details given beyond the oracle table; the optimization target was raising the teacher's solved-fraction.

## 5. What were the most important score-improvement tricks?
(Full table in `score_tricks.md`.) 1) **equation_numeric structural redesign** — 4 mutually-exclusive operator categories + exclusivity + **reversal symmetry shared across all examples**, global reversal by **majority vote**, family-exclusion guess (ties: sub > add > mul > concat) → deduce 95.3%, **guess 50.7% (highest in the batch)**. 2) **bit 3-input verification** (MAJORITY/XNOR) + bit-position-restricted search + left-edge fallback + drop parsing-display → 89.7%. 3) **Dataset rebalancing to 1:1 correct:incorrect** (keeps failed traces). 4) **Robust aggregation** (op valid if it matches ≥1 example, not all — handles symbol transcription errors). 5) **3-stage decreasing-LR SFT** (2e-4 → 2e-5 → 5e-6, upsample hard categories last).

## 6. What failure modes did the author avoid?
- **Avoided** strict all-example consistency (robust aggregation tolerates transcription noise).
- **Avoided** discarding teacher-incorrect traces (rebalanced 1:1 instead — keeping them).
- **Avoided** cryptarithm logical contradictions (non-operator-symbol fallback; format de-bracing).
- **Avoided** a single coarse SFT (3-stage: align → smooth → upsample-hard).

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?
- The **sharpest equation_numeric structural model** in this batch (reversal symmetry + family exclusivity), giving the **highest guess rate (50.7%)** — the **6th independent refutation** of our "equation = global cipher" verdict.
- vs **us**: LB13 **keeps teacher-incorrect traces and balances them 1:1** (echoing LB10's "excluding failed traces hurts") — our c1/c2 keep **only solver-correct** rows, so we likely discard useful signal. LB13 also uses a **3-stage decreasing-LR SFT** vs our single-stage runs. cryptarithm stays weak (~10%) — the top-end lever (LB1/LB3) it lacks. See `gap_analysis.md`.
