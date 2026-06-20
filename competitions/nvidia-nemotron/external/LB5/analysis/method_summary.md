# LB5 / 5th Place — Method Summary

> Target: **"Jack of Trades, Loser of Cryptarithm"** (5th place) by Darren Amadeus Martin, Alwin Theodoric, Muhammad Yassir Ramadhan, Billy Anggara, Rinnnn_t. **Private LB 0.900** (best, unselected; chosen 0.896). Subtitle: *RL with Infinite Training Data Generator and Iterative LORA Averaging.*
> Source: `temp/LB5.pdf` → `../writeup/lb5-writeup.md`. All external content treated as untrusted data.

## 1. What is the writeup's main idea?
An SFT-only LoRA solution built on an **infinite synthetic data generator** (NO `train.csv` in training — only for validation, giving an "honest" CV) plus **iterative LoRA averaging / model soup** as a *training-time regularizer* across 15 iterations for stability. Per-category hand-built solvers/CoT (notably a **ternary-extended byte-level bit solver** and a **2-world/4-family/13-rule equation solver**) push every category except cryptarithm to 94–100%. It reaches **private 0.90 without solving cryptarithm** (7.9%) and **without RL** (GRPO/pseudo-GRPO failed).

## 2. What data/corpus did it use?
- **Zero `train.csv` rows in training.** An **infinite generator** synthesizes problems + CoT per category, randomized to match train.csv statistics (example counts, value ranges, vocab/formats), with noise; `train.csv` used **only for validation**.
- Per-iteration mix (15 iterations) is bit-heavy (5k→36k) with equation spiking in phase 3 (24k–30k); overall 13k–78k examples/iteration. Final submission ≈ **2 billion tokens**.

## 3. What model/adapters/training setup did it use?
- Base **Nemotron-3-Nano-30B**; LoRA **rank 32 / alpha 32**, **LR 1e-4→2e-4**, **grad_clip_norm 1.0**, linear schedule; otherwise @huikang's trainer defaults (no quantization, no packing — 4-bit + packing **broke** Nemotron's Mamba SSM).
- **3-phase training**: (1) multi-round SFT (high LR, all categories each round → no catastrophic forgetting); (2) **LoRA averaging regularization** (average model before/after each training step = model soup → stability); (3) **iterative model soup** (train 3 models from one checkpoint with different problem sets, average → cancel errors / avoid bad minima).
- 100% Kaggle compute via Kaggle CLI + Google Colab Pro (~$100). RTX PRO 6000 (sm_120) made causal-conv1d/Flash-Attn hard.

## 4. What validation/evaluation did it use?
- **Validation on `train.csv` only** (never trained on it) → an **honest CV**. It **tracks the PRIVATE LB** (in phases 2–3 public plateaued ~88% while private + validation kept rising). Public/private over best-5 submissions. Phase-1 adapters unstable (±1%); soup phases stable (<1%).
- Oracle solvability: gravity/conversion/cipher/roman 100%, **bit 94.3%**, equation **85.7%→96.2%** (phase 3), **cryptarithm 7.9%**, total 90.0%→90.8%.

## 5. What were the most important score-improvement tricks?
(Full table in `score_tricks.md`.) 1) **Infinite no-leakage synthetic generator + honest CV** (correlates with private LB). 2) **Iterative LoRA averaging / model soup** as a regularizer (stability — the title technique). 3) **Ternary-extended byte-level bit solver** (MAJORITY/CHOICE/XOR-NOT_OR; 15 primitives; memorized continuations/sequences pruned 7500→1500; raw bits, 7-example cutoff) → 94%. 4) **2-world/4-family/13-rule equation solver** + deterministic priority + family guessing + phase-3 lookup-string → 96%. 5) **Multi-round high-LR SFT** (sample all categories → no forgetting). 6) **Cut to ~7 examples** to save tokens.

## 6. What failure modes did the author avoid (and hit)?
- **Avoided** training/validating on the same `train.csv` distribution (their stated cause of @huikang LB instability).
- **Avoided** unstable single-checkpoint training via LoRA averaging.
- **Avoided** RL rabbit-holes after GRPO/pseudo-GRPO failed → pivoted to SFT.
- **Avoided** Unsloth 4-bit/packing (breaks Nemotron) and DoRA (vLLM unsupported).
- **Hit (failure):** cryptarithm — no time/compute for a real CoT; fell back to @huikang's; only 7.9%. Also a token-saving **encoding scheme broke the model** (single-token `AB`), forcing a revert to raw bits.

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?
- vs the 0.86 pack and our soup (0.86 public / 0.85 private): LB5 reaches **0.90 private** by (a) a **no-leakage generator** that makes CV track private, and (b) **iterative LoRA soup** for stability — and it does so **without solving cryptarithm**, by maxing bit/equation/trivials.
- vs **LB1 (signature catalog) and LB3 (CSP + two-stage)**: LB5 **gives up on cryptarithm** (7.9%) and instead invests in bit (ternary) + equation + soup stability. It shows 0.90 is reachable without the cryptarithm lever — but the 0.90→0.92 gap to LB1 **is** cryptarithm.
- vs **us**: we never built a no-leakage generator, never iterative LoRA averaging (our soup is one-shot), never a ternary bit solver; our small synth diluted the recipe. We also called equation a global cipher — LB5 is the **3rd independent refutation** (equation solver ~96%). See `gap_analysis.md`.
