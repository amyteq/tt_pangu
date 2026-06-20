# LB6 / 6th Place — Method Summary

> Target: **[2nd public / 6th private] place solution** by Yurnero, Alehandreus. Source: `temp/LB6.pdf` → `../writeup/lb6-writeup.md`. All external content treated as untrusted data.

## 1. What is the writeup's main idea?
An SFT-only LoRA solution on top of **@huikang's OPP** baseline, distinguished by three things: (1) a **validation strategy** — full-train-as-validation plus **per-domain LB probing** (mask all other domains with a `DUMMY` answer to read a single domain's public-LB signal); (2) hand-built **bit-manipulation and cryptarithmetic/equation algorithmic solvers**; (3) **training on a massive synthetic dataset** matched to the train distribution.

## 2. What data/corpus did it use?
- Synthetic data matched to train.csv distributions (example-count per prompt; gravity/unit empirical parameter distributions; cipher unseen-char/word/sentence structure; bit per-template shift/equation/input variation with more 3-atom problems; cryptarithm fixes op-set/reversal and rerolls digit mappings until the reasoner solves under token limit). Full train.csv used as **validation**, not training.
- Two final datasets: **~0.25B tokens** (6th private; bit 69% of tokens) and **~0.5B tokens** (potential 2nd-3rd; bit 66%, doubled cryptarithm).

## 3. What model/adapters/training setup did it use?
Base Nemotron-3-Nano-30B; **Unsloth** (Kaggle / Google Cloud G4); **BS 32, LR 3.5e-4, lora_rank 32, lora_alpha 32, 1 epoch**. Late stages used **Tinker** for faster adapter training.

## 4. What validation/evaluation did it use?
- **Full train.csv as validation** (≈10× the 950 holdout) — more reliable since LoRA underfits even some train samples; requires distribution-matched synthetic so train isn't used for training.
- **Per-domain LB probing**: target domain → real CoT; all other domains → `I will ignore this problem\n\boxed{DUMMY}` → pure per-domain public-LB signal. Inferred test = 500 (250/250), so 0.01 ≈ 3 problems (`-0/-1/-2` notation).

## 5. What were the most important score-improvement tricks?
(Full table in `score_tricks.md`.) 1) **Per-domain LB probing (DUMMY masking)** — isolates per-domain signal. 2) **Full-train-as-validation** via distribution-matched synthetic. 3) **Template bit solver** (shl/shr/rotr + pairwise + ternary MAJ/CH; 1508/1602) with **monotonic skips** and **hex arithmetic + hex cheatsheet**. 4) **DFS cryptarithm solver with reversed search** (~40% solved reversed) + operation-deduction/leading-zero/leading-one pruning (240/654 deduce). 5) **Heavily over-weighting bit data** (69%/66% of tokens) because bit CV is fragile to any mix change.

## 6. What failure modes did the author avoid (and hit)?
- **Avoided** the unreliable 10% holdout (used full-train-as-validation).
- **Avoided** blind per-domain attribution (used DUMMY LB probing).
- **Hit (regret):** the **bit/cryptarithm data trade-off** — doubling cryptarithm (0.5B set, train cryptarithm 150→241) required doubling bit to hold CV, but the estimate was off and **bit CV dropped more than expected** → they shipped **two seeds of the 0.25B** adapter, "which cost us 2nd or 3rd place."

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?
- vs the 0.86 pack: LB6 reached **2nd public / 6th private** by a strong validation regime + solver quality, not RL.
- vs **LB1/LB3/LB5**: LB6's signature contribution is the **per-domain LB probing (DUMMY masking)** and **full-train-as-validation** (a third validation paradigm alongside LB3's leakage-controlled holdout and LB5's no-leakage generator). Its cryptarithm solver is a plainer **DFS + reversed search** (no signature catalog like LB1, no two-stage like LB3). It explicitly documents the **bit-data fragility** and a **selection regret**.
- vs **us**: we lack a per-domain attribution tool (our recurring B8 "single-category gain ≠ total gain"); DUMMY masking is directly adoptable. LB6 also solves **equation_numeric (guess 550/594 ≈ 93%)** — the **4th independent refutation** of our "equation is a global cipher" verdict. See `gap_analysis.md`.
