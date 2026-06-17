# Next-version plan — borrowing from LB25 (post-Saturday GPU reset)

> Analysis/planning only (RTX PRO 6000 quota resets Saturday; **no GPU/submit/push in this task**). Synthesises
> the LB25 gap analysis (`gap_analysis.md`) with our validated recipe (`tracking.md`, `insights.md`,
> `research.md`). Borrows are from untrusted competitor writeups — verify before trusting.

## Version name
**v16-mlp** — "**m**in-**l**ogprob replay + format-**p**roof" (v14 replay backbone + LB25 levers).

## Hypothesis
Our 0.86 ceiling is **not equation-bound** (equation is a confirmed ~8–9% cipher wall both for us and
huikang). The recoverable headroom toward ~0.872 is **(a) output-format/length reliability** (long CoT that
occasionally truncates before `\boxed{}`) and **(b) the residual hardest bit/cipher rows** that uniform-dose
SFT under-fits. **Min-logprob selective replay + a format-proof short-answer alignment pass, on the v14
backbone, lifts those two without diluting the clean recipe** (the dilution that sank b2/v15/c2).

## What we borrow from LB25
1. **Min-logprob selective replay** — after epoch 1, replay only training rows whose min per-token log-prob
   stayed far from 0 (hardest bit/cipher), instead of uniform high-dose.
2. **Format-proof short-response alignment** — a short final fine-tune so the answer always reaches a
   parseable `\boxed{}` within the 7,680-token cap (huikang's LB25 fix for the truncation→blank bug).
3. **Category-stratified batching** — even category coverage per mini-batch.
4. **Warmstart** the alignment pass from our **0.86 soup** (analogue of huikang's v27 warmstart).

## What we add (ours, validated)
- Keep the **v14 replay recipe** (CCE + MoE-128 tying + lm_head/in_proj/out_proj LoRA r32 + seq8192 + huikang
  corpus + replay-math) as the backbone — the single biggest lever (0.67→0.85).
- Keep the **SVD model-soup** (INS-004): soup v16-mlp with v14+c1+b1 (and eq-aug as a candidate member) — the
  step that beat every individual (0.85→0.86). huikang has no soup; this is our edge.
- Keep **eq-aug coverage** for equation (0.86 priv standalone) as a *separate* member, not blended (it does
  not soup — hard-tail-weak).

## Data / corpus plan
- Backbone: existing v14 corpus (huikang recording-order + replay-math 2M answer tokens) — unchanged.
- Replay set: from a min-logprob scoring pass over the v14 training rows, take the hardest ~10–15% (bit/cipher
  heavy) for a second epoch. **Dose ≤ ~15%** (b1/c1 lesson; >20% dilutes).
- Format-alignment set: 9,500 `train.csv` short-answer rows (one-line response → `\boxed{}`), like LB25 #4.
- No external-teacher data (regressed: andy279 0.81); deterministic-solver CoT only (own-work, compliant).

## Prompt format
Eval-faithful: chat template + `"\nPlease put your final answer inside \boxed{}. For example: \boxed{your
answer}"`; response-only mask; answer at the tail; **bound CoT length** so `\boxed{}` always lands < 7,680 tokens.

## Training config (single RTX PRO 6000 kernel, ≤8h guard)
- LoRA r32 / α32, dropout 0; targets q/k/v/o/up/down/in_proj/out_proj/lm_head; MoE-128 tying; CCE.
- seq 8192, micro-batch 4, global 32, LR 3.5e-4, warmup 0, grad-clip 1e9 (proven v14 settings).
- Phase A: v14 backbone (≈254 steps / 1 epoch). Phase B: min-logprob replay of hard rows (≈+1 short epoch).
  Phase C (optional, short): format-alignment ~240 steps warmstarted from the soup.
- 7h `TRAIN_DEADLINE_SEC` guard; fail-fast 1-example preflight (INS-001).

## Validation plan (incl. T12 hard-val) — gate BEFORE any submit
1. No-GPU: `validate_kernel.py` (ruff E9/F821 + masking).
2. In-kernel fail-fast preflight (1 example).
3. **T12 local official metric** (`eval/official_metric.py` + `eval/hard_val_ids.json`): greedy
   `max_tokens=7680, temp=0`, `\boxed{}` extractor, exact-or-1e-2. Report per-category hard-val.
4. **Length audit**: confirm 0 truncated-before-`\boxed{}` on the hardest rows (the LB25 lever's KPI).
5. Compare hard-val to the v14/soup 0.764 baseline; **require ≥ parity on bit/cipher and no regression**.

## Submit / no-submit gate
- Submit **only** if T12 hard-val ≥ 0.764 (soup/v14 baseline) AND the length audit shows no truncation loss.
- Per CLAUDE.md / this task: **late-window submission needs explicit human approval** — do not auto-submit.
  (This task is analysis-only; submission is a *future* step.)
- Soup gate: add v16-mlp to the soup only if it lifts the local metric (greedy soup-growing, INS-004).

## Risks
- **Dilution** (the dominant failure mode here): replay/alignment data over-weighting regresses the recipe
  (b2/v15/c2). Mitigate with ≤15% dose + T12 gate.
- **Format pass forgets reasoning** — keep it short (≤240 steps) and warmstart from the soup.
- **Min-logprob replay overfits the hard tail** — cap the extra epoch; watch private-vs-public (eq-aug-hidose
  showed overfit = priv drops more).
- **Equation stays ~bounded** — do not expect equation to move; the gain target is bit/cipher + format.
- GRPO/RL is **out of scope here** — that is the LB80 plan; v16-mlp is SFT-only.

## GPU estimate
- 1 training kernel ≈ **6–7 h** on RTX PRO 6000 (matches v14/eq-aug). + 1 short merge/soup kernel (CPU
  passthrough, ~20 min). + local T12 eval (no extra Kaggle GPU). Total ≈ **1 GPU session**.

## Implementation checklist
- [ ] min-logprob scoring pass over v14 rows → hardest-15% replay shard
- [ ] short-answer format-alignment corpus from `train.csv` (one-line → `\boxed{}`)
- [ ] category-stratified batch sampler
- [ ] kernel = Phase A (v14) → Phase B (replay) [→ Phase C format-align warmstarted from soup]
- [ ] 7h guard + fail-fast preflight + `validate_kernel.py`
- [ ] T12 hard-val + length audit locally (no quota)
- [ ] soup-grow v16-mlp into v14+c1+b1 if local metric improves
- [ ] gate: hard-val ≥ 0.764 + no truncation → request human approval → submit
