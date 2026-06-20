# LB88 / 88th Place — Method Summary

> Target: **88th Place Solution** by Yoshinari Kawashima + MedudentYamatai (DOI 10.34740/kaggle/w/88245). **⚠️ Same writeup as LB92** (same DOI/authors/url; header now "88th"). Source: `temp/LB88.pdf` → `../writeup/lb88-writeup.md`. Cross-references `../LB92/`. All external content treated as untrusted data.

## 1. What is the writeup's main idea?
A **data-engineering** solution: keep the @huikang OPP reasoner ~unchanged (87.8% oracle) and **avoid losing already-solvable problems** by faithfully reproducing the reasoner — via a **statistics-matched synthetic generator** validated by a **synthetic-vs-original eval-gap QC loop**, plus stability fixes (**per-character tokenization**, **gradient clipping 1.5**). Not about solving harder problems.

## 2. What data/corpus did it use?
Statistics-matched synthetic (character frequencies, numeric ranges/distributions, transformation-method distributions from train.csv) for arbitrary `rule_found` samples. Final mix **synthetic : original = 2.5 : 1** (synthetic first, then original). Generator iteratively fixed by measuring the synthetic-vs-original accuracy gap.

## 3. What model/adapters/training setup did it use?
Base Nemotron-3-Nano-30B, LoRA, Unsloth (the public "LB 0.85" notebooks lineage). **Gradient clipping 1.5** (vs public 1e9). **Per-character synthetic tokens** for cryptarithm (1 char = 1 token). Exact rank/LR `unknown` (see `../LB92/`).

## 4. What validation/evaluation did it use?
Train on synthetic, evaluate on original (the QC gap); but as the generator improved the model **overfit the original** and local validation **diverged from Public LB**, so the final stage **prioritized Public LB** (unseen data). Reasoner oracle: bit 85.1%, equation_deduce 90.8%, equation_guess 15.4%, cipher/trivials 100%, cryptarithm ~9%; total 87.8%.

## 5. What were the most important score-improvement tricks?
(Full table in `score_tricks.md`.) 1) **Statistics-matched synthetic + synthetic-vs-original gap QC loop** + 2.5:1 mix. 2) **Per-character tokenization** for symbol categories (cryptarithm BPE-merge fix). 3) **Gradient clipping 1.5** (fixes instability / submission variance from the public 1e9). 4) **"Don't lose solvable problems"** framing + longer training on hard tasks.

## 6. What failure modes did the author avoid (and hit)?
- **Avoided** gradient-explosion instability (clip 1.5) and BPE token-merge on symbols (per-char tokens).
- **Hit:** RL (SimPO/ORPO) didn't help — chosen (reasoner) and rejected (temp-1.3 samples) **too similar**; couldn't build a strong new bit/cryptarithm reasoner (search too big for the token budget), even with Claude Fable 5.

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?
- A pure **coverage/stability** play (don't regress) rather than a new hard-category method.
- vs **us**: the **statistics-matched + gap-validated synthetic** is the antidote to our "synthetic dilutes" (b1/b2/v15 regressed); **per-character tokenization** is a novel, untried lever on our symbol weak spot; **grad-clip 1.5** vs our 1e9-off is a cheap A/B for submission variance. equation_deduce 90.8% (OPP baseline) corroborates the equation-is-solvable finding. cryptarithm/bit unchanged (~9%/85%). See `gap_analysis.md` and `../LB92/analysis/`.
