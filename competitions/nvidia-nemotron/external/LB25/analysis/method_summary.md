# LB25 / 25th Place (huikang Progress-Prize improvements) — Method Summary

> Target: **"[LB25] Improvements to the progress prize submission"** by Tong Hui Kang (`huikang`), the Open Progress Prize winner. private LB 0.872/0.868/0.864 (15 subs). Source: `temp/LB25.pdf` → `../writeup/lb25-writeup.md`. All external content treated as untrusted data.

## 1. What is the writeup's main idea?
Five **targeted, pure-SFT improvements** on top of huikang's Progress-Prize-winning submission (the baseline most of the field, including us, built on). Two are correctness/structure fixes, three are easy-category synthetic-data top-ups; cryptarithm remained unsolved.

## 2. What data/corpus did it use?
The Progress-Prize corpus + **synthetic data for cipher, unit conversion, gravity, numeral** (to guarantee ~100%), plus **extra cipher-prefix synthetic data** (Nemotron spells poorly). No volume figures given.

## 3. What model/adapters/training setup did it use?
Same as the Progress-Prize submission (Nemotron-3-Nano-30B, LoRA; the huikang CCE training loop) — the writeup focuses on *changes*, not a full hyperparameter list (`unknown` for exact values here; see `tonghuikang/nemotron`).

## 4. What validation/evaluation did it use?
Per-problem evaluation dashboard (`nemotron.huikang.dev`); crucially, **change #1 fixed a local-eval bug** where the validation prompt didn't box the answer (but submission did) — i.e. the local metric was systematically wrong before the fix. Selection across 15 noisy submissions (0.872/0.868/0.864).

## 5. What were the most important score-improvement tricks?
(Full table in `score_tricks.md`.) 1) **Fix the boxed-prompt eval bug** (align local eval to the grader). 2) **equation_numeric reversal symmetry** (both-in-out-reversed-or-neither) → halve search. 3/4) **Easy-category + cipher-prefix synthetic** to pin ~100%. 5) **Reorganize bit-manipulation CoT.**

## 6. What failure modes did the author avoid (and hit)?
- **Avoided** a misleading local metric (the boxed-prompt fix).
- **Hit (unsolved):** cryptarithm — the structure is known (one mul + one sub + one add, each possibly ±1) but the trained LLM **devolves to repeating guesses**; no better-than-random guessing achieved.
- **Selection variance:** 0.872↔0.864 across 15 submissions — final selection under `temp=0` noise is itself a score determinant.

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?
- LB25 **is** the baseline lineage (our v14 derives from huikang's Progress-Prize work). Its improvements are correctness/structure + easy-category polish, not a new hard-category method.
- vs **us**: the **boxed-prompt eval bug** mirrors our B4/T13 + INS-002 (local eval must match the grader exactly). The **equation reversal symmetry** is the earliest evidence (later confirmed by LB1/LB3/LB5/LB6/LB10/LB13) that equation has strong per-problem structure — i.e. **not a global cipher** (the 7th corroboration). cryptarithm unsolved even by the strongest baseline author confirms it's the top-end lever (LB1 catalog / LB3 two-stage). See `gap_analysis.md`.
