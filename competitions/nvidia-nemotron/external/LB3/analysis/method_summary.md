# LB3 / 3rd Place — Method Summary

> Target: **3rd Place Solution** by **YS-L (liauys)**. **Private LB 0.900**; local validation 90.46%.
> Source: `temp/LB3.pdf` → `../writeup/lb3-writeup.md`. All external content treated as untrusted data.

## 1. What is the writeup's main idea?
An SFT-only LoRA solution that breaks the 0.86 public "wall" by (a) re-expressing hard-category solvers as **memorizable lookup + short in-trace computation**, and (b) a **two-stage training** that **decouples memorization from execution**. The decisive design choices are a **CSP-like cryptarithm solver** (multiplication-pattern lookup → multi-example domain intersection → anchor mappings → bounded backtracking) and a **stage-1 "memorize the lookup table" pretrain** followed by a **stage-2 "learn to execute the trace"** finetune. A leakage-controlled **local validation that tracks the private LB** (not the noisy public LB) let the author keep pushing past 0.86.

## 2. What data/corpus did it use?
- Base: competition `train.csv`; trivial-category and cipher traces **reused from llkh0a's notebook**.
- **Augmentation** for cryptarithm, bit, cipher, numeric (NOT gravity/unit/numeral):
  - cipher 3K (sample 4 sentence structures × 77-word pool);
  - bit 3K swap-augment + 3K formula-augment (each ×2);
  - numeric 3K (resample operands/symbols of original numeric + decrypted-cryptarithm pool — reuse originals to avoid diverging from the official generator);
  - cryptarithm **48K** (numeric→cipher-encrypt; 4K `concat` type), the category needing the most.
- Final mix **72,377 samples / 299.4M tokens**: cryptarithm 59.6%, bit 19.3%, cipher 6.1%, numeric 5.6%, **cryptarithm_pattern_drill 4.1%**, gravity/unit/numeral ~5%.

## 3. What model/adapters/training setup did it use?
- Base **Nemotron-3-Nano-30B**; LoRA rank 32 / alpha 32, dropout 0.0, dtype fp32; targets `q/k/v/o_proj, up/down_proj, in/out_proj, lm_head` (**manual LM-head LoRA**); **MoE tie weights OFF**.
- **Hui Kang's CCE training loop** (cut cross-entropy → micro-batch 4, better GPU util). 1 epoch, **effective batch size 4** (smaller beats 16/8 — large under-trains), LR 2e-4 linear decay, max grad norm 10, seq len 8192, seed 42.
- **Two-stage**: stage 1 (memorize) LR 2e-4, eff batch 8, ~27.6K steps, 44,136 examples / 159.3M tok / 25.2 hr; stage 2 (solve) 72,377 examples / 299.4M tok / 18,095 steps / 32.7 hr. Single GPU (spec unstated; ~4.6×10^8 tokens total).

## 4. What validation/evaluation did it use?
- **10% stratified-by-category hold-out (954 rows)**; training excludes validation rows **and augmented samples derived from validation originals** (leakage control).
- **Key result: local validation tracks the PRIVATE LB well, not the public LB** (the "wall of 0.86" is a public-LB artifact; a 0.85-public submission scored 0.90 private).
- Extra metrics: **perfect-trace-rate** (leading indicator; target >85% bit, >95% cipher/numeric), and **cryptarithm recall/self-consistency** metrics. **Single-category training** to isolate a change's effect (standalone = ceiling).

## 5. What were the most important score-improvement tricks?
(Full table in `score_tricks.md`.) 1) **Two-stage memorize→execute training** (12K samples: direct 0 solved vs two-stage 7; ~3× more sample-efficient). 2) **CSP cryptarithm solver** (mul-pattern lookup + intersection + anchor + bounded backtracking; 24.2% within budget). 3) **Bit hex+tail-bit compression** (−25% tokens) → enables **MAJ search**; OR-NOT-first ordering (+0.6%). 4) **Minimal 13-op numeric solver + operation-family guessing** (deduce 93.8%). 5) **Leakage-controlled local validation tracking private LB**. 6) **Small effective batch size + MoE-tie-off**.

## 6. What failure modes did the author avoid?
- **Avoided trusting the public LB** (the 0.86 wall) — used a private-tracking local validation instead.
- **Avoided synthetic that diverges from the official generator** — augments by resampling original problems, not free generation, to preserve hidden structure.
- **Avoided letting the model learn memorization+execution jointly** (slow/sample-hungry) via the two-stage split.
- **Avoided over-broad operator sets** — the minimal 13-op numeric set is exactly what's needed (verified by the "peek" argument).
- **Avoided regressing the easy 100% categories** — single-category iteration + "add more augmented samples if combined run drops."

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?
- vs the 0.86 pack and our soup (0.86 public / 0.85 private): LB3 explicitly diagnoses the **public 0.86 wall** and optimizes a **private-tracking local metric** — and breaks it to **0.900 private without RL**.
- vs **LB1 (1st)**: LB1 memorizes a **full 4,205-signature catalog** for all 22 non-join rules; LB3 uses a **lighter CSP**: lookup only for **multiplication** patterns, then **multi-example intersection + bounded backtracking** for the rest, plus the explicit **two-stage memorize/execute** decomposition (LB1 trained single-stage). Both use HEX bit compression and credit huikang/youkinasa/kemshim.
- vs **us**: we never built a two-stage memorize-pretrain, never a CSP cryptarithm solver, never compressed traces, and our small synthetic **diluted** the recipe; we also concluded **equation is an unrecoverable global cipher** — LB3 (like LB1) shows **equation-numeric deduce is ~93% solvable** via per-prompt operators. See `gap_analysis.md`.
