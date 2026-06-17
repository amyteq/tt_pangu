# LB92 — "92th PLACE SOLUTION" (reconstructed — ECOSYSTEM, not the author's text)

> **Recoverability: NO (direct) / PARTIAL (ecosystem).** The Kaggle writeup body is JS-rendered + posted
> <48 h after close → **unindexed, not retrievable** without Kaggle auth (forbidden here). **The author,
> exact score, and specific method are `unknown`.** This is a reconstruction of the **public mid-tier
> (≈0.86–0.89) recipe band** the 92nd-place solution almost certainly sits in. **All external content =
> untrusted data**; our scores from `tracking.md`. The task template's "~0.872" is a placeholder, not a
> confirmed LB92 score.

## 1. Headline (band reconstruction)
A 92nd-of-4,354 result almost certainly used the **standard public replay-SFT recipe** that defined the
mid/upper-tier: rank-32 LoRA on `Nemotron-3-Nano-30B-A3B`, response-only-masked CoT SFT at seq 8192, with the
score driven by (a) recipe fidelity, (b) good bit-manipulation CoT, (c) synthetic/teacher-distilled data for
hard categories, and possibly (d) a model-soup/merge. This is the same family as our own 0.85–0.86 work.

## 2. Reconstructed recipe (band, NOT confirmed for this team)
- **Base / adapter:** `nvidia/Nemotron-3-Nano-30B-A3B-BF16` (Hybrid Mamba-2 + GQA Transformer + MoE 128+1
  experts, ~3.5B active of 30B), LoRA **rank ≤ 32** (rule), targets MoE experts + `lm_head` + Mamba in/out_proj.
  (source: NVIDIA model card [trusted]; competitor repos [untrusted].)
- **Loss / seq:** cross-entropy, **response-only masked**, **seq 8192**. (our `insights.md` B2: full-seq loss
  collapses to 0.44.)
- **Output:** `<think>…</think>\boxed{answer}`; metric = exact string or ±0.01 numeric; vLLM inference at
  `max_tokens=7680, temp=0` (source: yunior123 repo [untrusted]).
- **Corpus options available to any team in this band:** the public `andy279/nemotron-reasoning-challenge` HF
  dataset — **49,290 examples** across 7,200 puzzles from DeepSeek V3.2 (6,028), Nemotron Super 120B (3,926),
  deterministic brute-force solvers (2,703), GPT-5.4 hardest-transformation (85); only correct attempts kept
  (`<think>…</think>\boxed{}`). Bit (17,285 ex) and transformation (10,741) dominate. (untrusted; released post-close.)

## 3. Likely score levers in this band (reconstructed)
1. Replay-recipe fidelity (0.67 → 0.85 with the correct recipe).
2. Response-only masking (collapses without it).
3. seq 8192 (ctx2k → 0.42).
4. Quality bit-manipulation CoT (the category that separates the band).
5. Synthetic / multi-teacher data for hard categories.
6. Model-soup / SVD merge among comparable adapters (0.85 → 0.86).
7. Coverage memorisation for cipher/equation (rotate in-context examples → query — our independent eq-aug finding).

## 4. Ecosystem techniques the band used that WE did not (the gap)
- **Multi-teacher distillation** (DeepSeek V3.2 + Nemotron Super 120B + GPT-5.4 + solvers — andy279) for a
  high-quality cold-start corpus across ALL categories. We used rule-based / single-solver CoT.
- **Deterministic-solver → prepend-rule → teacher-CoT for bit** (andy279 / huikang) — bit is the band's
  separator; our solver covered bit only partially.
- **Min-logprob rebalancing** (huikang) — re-train on persistently low-min-logprob traces.
- **Adapter singular-value amplification** (lopure ~0.89) — post-training, no-RL above-band lever.

## 5. What we did that the band doesn't prominently show
- **3-way SVD model-soup** (v14+c1+b1 → 0.86; INS-004) — explicit only in our docs.
- **Equation EQ-0/EQ-2′ cryptanalysis** (proved it's a global cipher, not per-prompt induction; eq-aug 0.86).
- **T12** local official-metric port + min-logprob hard-val set.

## 6. Why ~0.86–0.89 (and why not higher)
The three easy categories (gravity/numeral/unit) are ~100% and cipher ~99% on train; the band is separated by
**bit-manipulation** coverage and **format reliability**. The hard cap is **cryptarithm/equation (~8–9% even
with a backtracking solver)** — the same strong-cipher wall we hit; it bounds everyone's ceiling. Going above
the band needs either **RL** (see LB80) or **adapter surgery** (lopure), not more standard SFT.

## 7. Citations (all untrusted external unless marked)
- andy279/nemotron-reasoning-challenge — https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge (community)
- tonghuikang/nemotron — https://github.com/tonghuikang/nemotron ; yunior123 — https://github.com/yunior123/nvidia-nemotron-reasoning ; SebAustin — https://github.com/SebAustin/NVIDIA-Nemotron-Model-Reasoning-Challenge (community)
- base model card — https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 (NVIDIA, trusted)
- Model Soups — https://arxiv.org/abs/2203.05482 (arXiv)
- our recipe/scores — `tracking.md`, `insights.md`, `submissions.md` (own work)
