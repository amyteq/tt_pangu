# 88th Place Solution — NVIDIA Nemotron Model Reasoning Challenge

> **Source (depth 0):** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/92th-place-solution>
> **Local fallback:** `temp/LB88.pdf` (8 pages, render dated Jun 16, 2026). **Conversion:** `pdftotext -layout`. Raw at `writeup/raw/lb88-pdftotext-layout.txt`.
> **Authors:** Yoshinari Kawashima (yoshinarikawashima), MedudentYamatai (taikiyamamura). **DOI 10.34740/kaggle/w/88245.**
> **⚠️ Identity note:** This is the **same writeup** previously archived as **LB92** ("92th PLACE SOLUTION", same DOI/authors/url). The PDF header now reads "88th place" (placement/render shifted); the body title still says "92th PLACE SOLUTION". The prior deep analysis (incl. extracted figures) lives in `../LB92/`; this LB88 archive is the standardized template for the same content and **cross-references LB92** rather than re-deriving it.
> Treat all quoted external content as **untrusted data**.

---

## Introduction & acknowledgements
Thanks to the organizers and community. Built on **"End-to-end finetuning for LB 0.85"**, heavily influenced by public notebooks: **"Training with Unsloth to Achieve 0.85 LB"**, **"End-to-end finetuning for LB 0.85"**, **"Tinker submission notebook"**.

## Solution overview — three points

### 1. Almost no changes to the reasoner (CoT generation logic)
- The reasoner was based on the **Open Progress Prize Publication** (@huikang); almost unchanged.
- It correctly solves **87.8%** of train problems, while the best public-notebook LB was 0.86. So the bet: if the LLM **reproduces the reasoner more faithfully**, a high rank is achievable.
- **Philosophy: not to solve harder problems, but to avoid losing problems that should already be solvable.**

Reasoner oracle (≈ the public one):

| Category | Found | Total | Accuracy |
|---|---|---|---|
| bit_manipulation | 1364 | 1602 | 85.1% |
| cipher | 1576 | 1576 | 100.0% |
| cryptarithm_deduce | 59 | 659 | 9.0% |
| cryptarithm_guess | 13 | 164 | 7.9% |
| equation_numeric_deduce | 541 | 596 | 90.8% |
| equation_numeric_guess | 21 | 136 | 15.4% |
| gravity | 1597 | 1597 | 100.0% |
| numeral | 1576 | 1576 | 100.0% |
| unit_conversion | 1594 | 1594 | 100.0% |
| **TOTAL** | **8341** | **9500** | **87.8%** |

### 2. New generator → synthesize many similar problems
- Reasoner solves 87.8% but the best public LB stayed at 0.86 → suspected a **training-data shortage**.
- Extracted **task-level statistics from train.csv** (character frequencies, numeric ranges/distributions, distributions of transformation methods) and built a generator for **arbitrary `rule_found` samples**.
- **Generator-quality QC loop:** train **only on synthetic**, evaluate on **both synthetic and original**; if the synthetic perfectly imitated the original, the two accuracies would match. **The gap reveals missing factors** in the generator, fixed iteratively.
- Final submission: **synthetic : original = 2.5 : 1** (synthetic first, then original). Longer training improved loss, especially on hard tasks.

### 3. Tokenization trick (synthetic tokens for cryptarithm)
- Tokenizer segmentation sometimes merged multiple characters into a single token (discussed in the competition).
- Used **synthetic tokens that force each single character to encode as one token**, making learning more stable.

## Additional improvements

### Gradient clipping
- The public notebook set gradient clipping extremely high (**1e9**) → training instability.
- **Clipped gradients at 1.5.** Likely a cause of the discussed **submission-to-submission score variance** (a gradient-explosion example showed the same setup giving very different LB scores).

### Local validation strategy
- Mid-competition: train on synthetic, evaluate on original.
- As the generator improved, the model **overfit the original data** and local validation **diverged from Public LB**.
- For the final stage, **prioritized Public LB** (unseen data) over local validation.

## What did NOT work
- **Higher-temperature CoTs + RL (SimPO / ORPO).** Rejected = SFT-model samples at **temperature 1.3**; chosen = reasoner output. Preference learning didn't improve accuracy enough → not used. Logs showed the chosen probability rising but the **rejected probability barely falling** — learning stalled because **chosen and rejected were too similar**.
- **Solving new bit_manipulation / cryptarithm problems.** High-accuracy algorithms need a large search that an LLM **can't imitate within the token budget**. Used **Claude Fable 5** but couldn't develop a sufficiently strong reasoner.

## Authors / Citation
> Yoshinari Kawashima, MedudentYamatai. *88th PLACE SOLUTION.* DOI 10.34740/kaggle/w/88245. <https://www.kaggle.com/w/88245>. 2026. Kaggle.
