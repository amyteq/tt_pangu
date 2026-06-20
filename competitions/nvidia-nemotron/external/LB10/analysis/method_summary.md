# LB10 / 10th Place — Method Summary

> Target: **10th Place Solution** by Rick (rikitomo0526), neilus, eikichi. **Public 0.860 / Private 0.880.** Source: `temp/LB10.pdf` → `../writeup/lb10-writeup.md`. All external content treated as untrusted data.

## 1. What is the writeup's main idea?
**Deterministic program-generated reasoning traces** (not LLM distillation): per-category symbolic reasoners re-derive the answer from the prompt alone (never reading ground truth), emit step-by-step CoT ending in `\boxed{}`, and a single base model is SFT'd with LoRA to imitate the **procedure**. The thesis: **score is bounded by the deterministic teacher's oracle coverage**, so the main lever is improving trace coverage/learnability, not SFT hyperparameters.

## 2. What data/corpus did it use?
Synthetic problems with program-generated CoT across 9 categories. Full training data, no OOF exclusion; samples >8192 tokens dropped (e.g. 1578/1602 bit traces kept). Prompt tokens masked (mask=0); train only on completion tokens (mask=1). Priority samples (fragile failure modes / y-trap bit / dictionary-search cipher) duplicated 2×; low-logprob problems added/duplicated and retrained.

## 3. What model/adapters/training setup did it use?
Base `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` (30B MoE, ~3B active). LoRA **rank 32, alpha 128 (alpha/r = 4)**, dropout 0.0; targets q/k/v/o + in/out + up/down_proj + **lm_head**; max_seq 8192; LR 2e-4 linear (warmup 0); **2 epochs**; effective batch 32; stratified sampling.

## 4. What validation/evaluation did it use?
- **950 held-out**, per-category accuracy.
- **Oracle ceiling vs fidelity** — model accuracy vs the reasoner's oracle accuracy to separate "reasoner wrong" from "model failed to imitate."
- **Learnability analysis** — per-example/per-epoch log-probs to find hard/fragile traces.
- **Selected by validation, not public LB** → better private (best private run: val 0.904, public 0.860, private 0.880; the discarded public-best run: val 0.876, public 0.872, private 0.852).

## 5. What were the most important score-improvement tricks?
(Full table in `score_tricks.md`.) 1) **bit_manipulation rewrite** to a **rotate/shift key-table reasoner** (`out[i]=F(rotl,shl,shr)`, F read as a 3-bit-key→bit table; recover (a,b,c) from boundary bits) → oracle **85.14% → 98.75%**, with shorter traces. 2) **equation_numeric**: deduce candidate reorder by frequency (+14) and guess two-axis rebuild (operation + wrapper, +35 → 56/136). 3) **alpha/r = 4** (high LoRA alpha) to follow the deterministic CoT. 4) **Add low-logprob problems + failure-mode demos (2×)** and retrain. 5) **Select by validation, not public LB.**

## 6. What failure modes did the author avoid (and surprising negatives)?
- **Avoided** trace bloat / runaway loops (removed per-example echoes + candidate enumeration).
- **Avoided** public-LB overfitting (selected by validation).
- **Surprising negatives:** **excluding failed / low-confidence reasoner traces DECREASED accuracy** (failure patterns carry useful signal); **LoRA merge (SVD + seed soup) both failed** to beat the single best adapter; **two-stage training** redistributed wins/losses (single-stage mixing more stable); **3× priority overfit**; **curriculum learning** did nothing; **cryptarithm add/sub/mul traces** were too jumpy to learn.

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?
- The cleanest articulation of **"improve the teacher, not the training"** (score = oracle ceiling). vs LB1/LB3/LB5/LB6, LB10's bit solver is a **rotate/shift key-table** read from examples (boundary-bit two-input trick) rather than enumeration.
- vs **us**: two direct challenges — (a) **excluding failed traces HURT** LB10, but our c1/c2 keep **only solver-correct** rows; we may be discarding useful failure-pattern signal. (b) **LoRA merge failed** for LB10 (rank-32 SVD can't extract complementarity; seed soup → worst member) — a tension with our soup +0.01 and LB5's iterative soup; merge gains are member/averaging-dependent, not universal.
- equation_deduce 93.1% / guess 41.2% — the **5th independent refutation** of our "equation is a global cipher" verdict. See `gap_analysis.md`.
