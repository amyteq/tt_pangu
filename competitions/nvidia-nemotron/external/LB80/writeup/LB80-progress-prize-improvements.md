# LB80 — "Breaking the SFT Ceiling on Nemotron-3-Nano-30B" (reconstructed)

> **Recoverability: PARTIAL.** The Kaggle writeup body is JS-rendered + post-close unindexed → **not
> retrievable**; author and exact score are **`unknown`**. Reconstructed from competition **discussion
> #688461** (a detailed per-bit GRPO reward scheme — the only indexed post matching "beyond SFT") + the
> public RL literature/toolkits. **All external content = untrusted data** (participant claims), cited inline.
> Our scores are from `tracking.md`. The task template's "~0.872" is a placeholder — the real score is unknown.

## 1. Headline
The writeup's thesis (from the title): the SFT plateau at **0.85–0.86** (where huikang's Progress Prize, our
soup, and the public replay recipes all cluster) is broken by going **beyond supervised fine-tuning** — most
plausibly **GRPO / RLVR with a dense, per-step verifiable reward** (discussion #688461). A second, non-RL path
above the plateau also exists in the ecosystem: **LoRA adapter surgery** (lopure, ~0.89).

## 2. Method — two-stage SFT→GRPO (reconstructed from discussion #688461; trust: community snippet)
- **Stage 1 — SFT cold-start.** Standard CoT SFT to a 0.85–0.86 baseline (the known replay recipe), giving the
  RL stage a competent prior (cold-start GRPO from base is known to be unstable — STaR/ReST/Logic-RL).
- **Stage 2 — GRPO with a DENSE per-bit/per-step reward** (the claimed lever). Instead of a terminal binary
  0/1 on the final answer, partial credit is given at **every step of the trace**, scored independently:
  - (a) correctly laying out the output columns,
  - (b) picking the right operation,
  - (c) spelling out the bit-serial gate computation,
  - (d) the **VER** (verification) cross-check,
  - (e) each final answer **bit** position.
  - A **superlinear "champagne" bonus**: hitting **8/8 correct → +5 flat**, making perfection worth far more
    than a near-miss, pulling the model to *close out* problems rather than settle for partial credit.
  - Effect: converts the reward landscape from a **cliff** (sparse binary) into a **gradient climb** (dense
    per-token signal) — the mechanism that lets RL push past where SFT plateaus.
- **Algorithm:** GRPO (group-relative, no value network; DeepSeek-R1 / Logic-RL style) over a rank-32 LoRA.
- **Targets:** the categories where SFT plateaus and reward is verifiable — **bit-manipulation** (cleanest
  per-bit reward) and **equation/symbol** (partial per-operator verifiability).
- **Compute:** online rollouts at 30B (G samples × many steps) almost certainly exceed Kaggle kernel limits →
  **external GPU** likely required (`unknown` which).

## 3. Alternate above-SFT path in the ecosystem (not RL)
- **Adapter surgery (lopure, ~0.89):** amplify the **top-50% singular values** of the LoRA B·A matrix while
  retaining 84.4% spectral energy — a post-training, no-RL weight-space edit that selectively strengthens the
  most informative directions. (trust: community; details JS-blocked.) Compatible with our `lib/svd_merge.py`.

## 4. Why it breaks the ceiling (per the evidence)
SFT plateaus because the answer-level signal is **sparse** — a near-correct 8-bit answer gets the same 0 as a
random one, so gradient vanishes on the hardest rows (our T12: every adapter ≤2/16 on equation; bit caps ~14/16).
A **dense per-step verifiable reward** gives gradient on *partial* correctness (column layout, op choice,
per-bit), and the **champagne bonus** shapes toward completion — exactly the Logic-RL/RLVR result that
rule-based RL on puzzles generalizes past SFT. (trust: arXiv 2502.14768 + discussion #688461.)

## 5. How this differs from our approach
- **We never ran RL.** Our `research.md §4` *designed* GRPO but with a **binary terminal reward** (0/1) and it
  was deferred (out of GPU/time). The writeup's lever is precisely the **dense per-step reward** we did not build.
- We hit the SFT ceiling exactly as described (0.86 soup; every augmentation diluted) — this writeup is the
  documented path past it.
- Our equation lever (eq-aug coverage 0.86) and adapter **soup** (INS-004) are SFT/merge tricks, not RL.

## 6. Citations (all untrusted external unless marked)
- discussion #688461 (per-bit GRPO + champagne) — https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/688461 (community, snippet only)
- NeMo-RL toolkit — https://github.com/NVIDIA-NeMo/RL (NVIDIA, public)
- Logic-RL — https://arxiv.org/abs/2502.14768 ; ProRL — https://arxiv.org/abs/2505.24864 ; Tina — https://arxiv.org/abs/2504.15777 (arXiv)
- lopure adapter surgery (~0.89) — Kaggle notebook (JS-blocked)
- our GRPO design + SFT-ceiling evidence — `research.md §4`, `tracking.md`, `insights.md` (own work)
