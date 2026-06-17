# Next-version plan — borrowing from LB92 (post-Saturday GPU reset)

> Analysis/planning only (no GPU/submit/push in this task). The LB92 contribution is the **corpus-quality**
> lever (multi-teacher + solver-prepend bit CoT + min-logprob rebalancing). Borrows are from untrusted
> competitor sources — verify before trusting; the 92nd-place specifics are `unknown`. Complements the LB25
> (`v16-mlp`, replay/format) and LB80 (`v17-grpo`, RL) plans.

## Version name
**v18-corpus** — "richer cold-start corpus: solver-prepend bit CoT + multi-teacher (low-dose)".

## Hypothesis
Our 0.86 already sits in the mid-tier band; the band's edge is **corpus quality for bit-manipulation** (the
separator category, our most train-set headroom). A **deterministic-solver-prepend bit CoT** (solver finds the
rule → prepend → clean step-by-step trace) + **min-logprob rebalancing** of the residual hard bit rows, woven
at low dose into the v14 backbone, lifts bit without diluting the recipe — and souping the result keeps the 0.86.

## What we borrow from LB92 (band)
1. **Solver-prepend bit CoT** (andy279/huikang pattern) — the highest-quality, own-work bit reasoning data.
2. **Min-logprob rebalancing** — re-train only on persistently low-min-logprob bit/cipher traces.
3. (⚠ rules-gated) **multi-teacher distillation breadth** — only as a **low-dose cold-start** (our prior
   external-teacher run regressed at high dose, 0.81).

## What we add (ours, validated)
- v14 replay backbone (the biggest lever) + **SVD model-soup** (INS-004; we're ahead of the single-adapter band).
- Reuse `eval/official_metric.verify` to keep only solver-CoT whose answer matches ground truth (own-work, compliant).
- Keep **eq-aug** standalone for equation.

## Data / corpus plan
- **Expand `lib/nemo_solver.py` bit coverage**: emit huikang-style column-match diagnostic traces; keep only
  verified-correct (answer == gold). Target the bit rows our current solver misses (bit train ceiling ~86%).
- **Low dose** (≤~10–15%, per the b1/c1 lesson — high dose diluted: b2/v15/c2/andy279 all regressed).
- min-logprob rebalancing shard: hardest residual bit/cipher rows for a short second pass.
- **No high-dose external-teacher data** (regressed to 0.81); solver-prepend own-work CoT preferred.

## Prompt format
Eval-faithful (chat template + `\boxed{}` SUFFIX), response-only mask, bounded CoT length (< 7,680 cap — the LB25 lesson).

## Training config (single RTX PRO 6000 kernel, ≤8h guard)
- LoRA r32/α32; MoE-128 tying; lm_head/attn/in_proj/out_proj; CCE; seq 8192; LR 3.5e-4; micro 4 / global 32.
- Phase A: v14 backbone. Phase B: weave solver-prepend bit CoT (≤15%) + min-logprob rebalancing pass.
- 7h `TRAIN_DEADLINE_SEC` guard + fail-fast 1-example preflight (INS-001).

## Validation plan (incl. T12 hard-val) — gate BEFORE any submit
1. `validate_kernel.py` (ruff E9/F821 + masking); in-kernel fail-fast preflight.
2. **T12 local official metric** on `eval/hard_val_ids.json` (greedy 7680/temp 0, exact-or-1e-2), per category.
3. **Require bit hard-val ↑ vs v14/soup 0.764 baseline, no regression on cipher/easy cats** (anti-dilution).
4. CoT-length audit (no truncation before `\boxed{}`).

## Submit / no-submit gate
- Submit only if T12 hard-val ≥ 0.764 AND bit ↑ AND no easy-cat regression.
- **Late-window submission needs explicit human approval** (this task is analysis-only).
- Soup-grow v18-corpus into v14+c1+b1 only if the local metric improves.

## Risks
- **Dilution** (dominant failure mode): bit/teacher data over-weighting regresses (b2/v15/c2/andy279). Mitigate ≤15% dose + T12 gate.
- **Compliance:** external-teacher traces must satisfy competition/data rules — verify first; prefer own-solver CoT.
- **Equation won't move** — bounded ~8–9%; target bit, not equation.
- **Solver coverage:** if the expanded bit solver still misses the hardest multi-op rules, the gain is capped (matches the ~86% bit train ceiling).

## GPU estimate
- 1 training kernel ≈ **6–7 h** on RTX PRO 6000 + 1 short soup kernel (CPU, ~20 min) + local T12 (no extra GPU).
  Total ≈ **1 GPU session** (data-side work, like `v16-mlp`; cheaper than the LB80 RL plan).

## Implementation checklist
- [ ] expand `lib/nemo_solver.py` bit solver → verified solver-prepend bit CoT corpus (answer == gold)
- [ ] min-logprob rebalancing shard (hardest residual bit/cipher rows)
- [ ] weave at ≤15% dose into the v14 backbone kernel
- [ ] (if rules permit) low-dose multi-teacher cold-start; else own-solver CoT only
- [ ] 7h guard + fail-fast preflight + `validate_kernel.py`
- [ ] T12 hard-val + length audit locally (no quota)
- [ ] gate: bit hard-val ↑, no easy-cat regression → request human approval → submit
- [ ] soup-grow v18-corpus into v14+c1+b1 if local metric improves
