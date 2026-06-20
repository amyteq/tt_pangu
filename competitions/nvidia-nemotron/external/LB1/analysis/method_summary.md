# LB1 / 1st Place — Method Summary

> Target: **1st Place Solution** (GoodMeatDay, re, reopon). Public **0.91** / Private **0.920** (best unselected 0.932).
> Source: `temp/LB1.pdf` → `../writeup/lb1-writeup.md`. All external content treated as untrusted data.

## 1. What is the writeup's main idea?

A deliberate **memorization-vs-computation split** for an SFT-only LoRA submission. Because the grader forbids running any program at eval time (vLLM, `temp=0`, `max_tokens=7680`, `\boxed{}` exact/1e-2 match), every "solver" must be re-expressed as an SFT trace the model replays within 7680 tokens. The team decided, per category, **what the model should memorize** (precomputed catalogs) and **what it should compute** (short consistency checks / DFS) inside the trace. The pipeline is plain: generate synthetic problems programmatically → attach rule-based-solver traces → SFT. The win came from solving the two long-tail categories (**cryptarithm** and **bit manipulation**) decisively rather than uniformly nudging all categories.

## 2. What data/corpus did it use?

- Base: provided `train.csv` (9,500 labeled problems across 7 categories), used to **extract statistics**, not just as training rows.
- **Programmatically generated synthetic problems** (NOT LLM-written): sample a prompt skeleton from train statistics (number of equations, distinct operators, whether the query operator is seen, difficulty class), instantiate hidden rules/values, render with competition-matching templates, run a rule-based solver to attach the trace, keep only internally consistent puzzles.
- Volume: **main training 220,000 samples / 890.1M tokens**; **extra training pool 140,000 samples / 590.7M tokens** (extra run actually processed ~104,000 samples / 6,500 steps). Per-category split heavily favors the hard categories: cryptarithm 120k main + 40k extra; bit 40k main + 50k extra. Validation = 15% split from train.csv (1,424 samples).

## 3. What model/adapters/training setup did it use?

- Base **Nemotron-3-Nano-30B**; submission is a **LoRA adapter, rank ≤ 32**.
- LoRA rank 32, alpha 32; target modules `q_proj, k_proj, v_proj, o_proj, in_proj, out_proj, up_proj, down_proj, gate_proj, lm_head`.
- Optimizer `adamw_bnb_8bit`, cosine scheduler. **Main LR 2.0e-4, 1.0 epoch, ~119h; extra (continuation) LR 1.0e-5, 6,500 steps, ~51h.** Per-device batch size main 1 / extra 2; effective batch size 16.
- Framework **Unsloth**. Hardware: a **single NVIDIA RTX PRO 6000 Blackwell** in a personal workstation (~2.3h per 20M tokens; >1B tokens total). All code written via **Codex** (ideas/trace design were human).

## 4. What validation/evaluation did it use?

- A **15% train split** for local validation, but **GPU capacity was too limited to evaluate many checkpoints live**. So they periodically **submitted to Kaggle and used Public LB as a noisy external signal**; local validation (run later) correlated reasonably with the Public LB trend.
- They also tabulated **solver coverage vs model accuracy within the 7680-token budget** per category (self-described as leakage-prone, since solvers were built after seeing all of train).
- Explicitly acknowledged: `temp=0` is **not fully deterministic**, Private LB fluctuates heavily across nearby checkpoints. Final pick = the extra-trained adapter, submitted twice.

## 5. What were the most important score-improvement tricks?

(Full table in `score_tricks.md`.) Ranked by attributed impact:

1. **Cryptarithm signature catalog + candidate-count memorization + DFS** — the single biggest lever; pushed cryptarithm path to Public 0.89 / Private 0.908.
2. **Bit manipulation: HEX compression of bit columns** — median generated tokens 6771 → 4888 (−27.8%), freeing budget to cover more rule families.
3. **Bit manipulation: rule-sequence catalog + Hamming-distance repair** — nearest-neighbor projection of the heuristically-selected 8-rule sequence onto 5,238 valid sequences; with extra training took the system to Public 0.91 / Private 0.920.
4. **Added bit rule families** (majority, par3, ch, sel_nand_xnor, ao/oa/ax/ox/xa/xo) — coverage the original @huikang solver gave up on.
5. **24-rule inventory + Observation 1 (mode) + Observation 2 (group)** — shared across equation-numeric and cryptarithm for pruning.
6. **77-word plaintext vocabulary** constraint for text cipher; operator priors for equation numeric.
7. **Extra/continuation training** weighted toward bit manipulation at low LR (1e-5).

## 6. What failure modes did the author avoid?

- **Avoided "uniform nudge" across categories** — they targeted a clear gap in exactly the two categories where the 0.86 pack was stuck, instead of small gains everywhere that LB variance could erase.
- **Avoided diluting the recipe with low-value synthetic data** — kept the bit rule set compact (add/remove while preserving train coverage) rather than enumerating an unnecessarily broad rule space.
- **Avoided trusting the heuristic bit selection blindly** — repair rejects sequences not in the catalog (e.g. `default 1` fallbacks) and projects onto valid transformations.
- **Avoided LLM-authored synthetic puzzles** — programmatic generation enforcing the two observations kept puzzles internally consistent and on-distribution.
- **Avoided over-reading the noisy LB** — used LB only as a coarse external signal and cross-checked against local validation; accepted selection variance as a known risk.

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?

- The 0.86 pack (and our best, soup 0.86 public / 0.85 private) reached the **clean-SFT ceiling**. LB1 broke it **without RL**, purely by re-expressing hard-category solvers as **memorizable catalogs verified by short in-trace computation**.
- Versus **@huikang's Open Progress Prize** (the acknowledged starting point): @huikang's public code has the per-output-bit bit solver and a backtracking cryptarithm DFS, but **no HEX compression, no signature catalog, no rule-sequence catalog, no Hamming repair, no candidate-count memorization** — these are LB1's additions (confirmed by inspecting `github.com/tonghuikang/nemotron`; see `source_index.md`).
- Versus **our attempts**: we synthesized cryptarithm/bit data (b1/b2/v15/c1/c2) and merged/souped (0.86), but (a) never compressed traces (HEX), (b) never built a memorizable signature/rule-sequence catalog with candidate counts, and (c) our augmentation **diluted** the clean replay recipe and regressed the hard slice. We also concluded **equation numeric is an unrecoverable global cipher** (EQ-0/EQ-2′), whereas LB1's coverage table shows **equation-numeric *deduce* is ~95% solvable** via per-prompt operator inference over the 24-rule inventory — a premise we must re-check. See `gap_analysis.md`.
