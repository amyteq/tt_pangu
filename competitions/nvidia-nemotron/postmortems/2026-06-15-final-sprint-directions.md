# Final-sprint research + chosen directions (nemo, 2026-06-15, ~12h to deadline)

> Goal: push past our standing best **0.86** (own-work SVD soup v14+c1+b1) in the last window.
> Inputs: T12 hard-val ranking (soup/v14 robust; c1/c2/v15 regress hard cipher/bit; `equation`
> unsolved by all ≤2/16), a competition-research sweep (forum/code/HF/arXiv), and slot/time limits
> (deadline 2026-06-15 23:59 UTC; quota won't reset before close).

## Research synthesis (cited; trust labelled)

**Cheap post-hoc lever — spectral / SVD surgery on a trained adapter (no training):**
- **Spectral Surgery** ([arXiv 2603.03995](https://arxiv.org/pdf/2603.03995), trusted) — SVD-decompose each LoRA delta, **reweight singular values** (keep directions fixed) under an energy constraint, calibrated on a small set; "+2–4 pts", "the learned spectrum is a primary post-training bottleneck", modifies O(r) scalars, **rank-preserving**. Corroborated by [Make LoRA Great Again](https://arxiv.org/abs/2502.16894), [Primacy of Magnitude in LoRA](https://arxiv.org/pdf/2507.06558).
- **lopure's notebook** "amplify-top-50-singular-value-retain-84.4%-energy" ([Kaggle](https://www.kaggle.com/code/lopure/amplify-top-50-singular-value-retain-84-4-energy), community/low — title only; code JS-rendered) — a competition instance of the above on a Nemotron adapter: keep top singular vectors to 84.4% cumulative energy, amplify, applied to all LoRA modules. ⚠ Caveat: amplifying a well-calibrated adapter *can* hurt; risk is bounded (LB keeps the max) and it's gated locally on hard-val here.

**Merge methods** ([survey](https://loraexchange.ai/guides/merging_adapters/)): DARE (drop ~90% deltas + amplify), TIES (sign-align/trim), KnOTS (SVD-align subspaces) can beat a plain weighted soup — but T12 shows our augmented members (c1/c2/v15) are weak on hard problems, so re-merging them mostly dilutes; the merge ceiling from the existing pool is ~0.86–0.87.

**Frontier — the `equation`/`bit` categories (the 0.85→0.87+ differentiator):**
- The proven public pattern is **solver-guided teacher CoT**: brute-force the hidden rule from the examples, then a strong teacher writes a CoT that *states the rule first* — qualitatively stronger than our template/synth CoT. Publicly available pre-made in [andy279/nemotron-reasoning-challenge](https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge) (trusted_public): 50,455 correct-only traces incl. ~2,703 solver-guided bit+transformation traces (teachers: DeepSeek V3.2, Nemotron-Super-120B, GPT-5.4). Reported ~0.87 territory (inferred).
- **kuangyicheng short-format alignment (~0.87)** ([discussion #703896](https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/703896), community/medium): long-CoT replay adapters can hit `max_new_tokens=7680` *before* emitting `\boxed{}` on hard problems → empty answer. ~240-step fine-tune on SHORT responses re-aligns the format and recovers them.

**Against more self-distillation (validates the v11 stand-down):** rejection-sampling CoT shows "diminishing returns near saturation" and self-distillation hits "rapid policy saturation/degradation — the student shares the teacher's biases" ([on-policy distillation survey](https://arxiv.org/pdf/2604.00626), [Why Self-Distillation Degrades Reasoning](https://arxiv.org/html/2603.24472v2)). Only an *external* teacher breaks the plateau.

**Rules (⚠ verify on the official page):** synthetic data generation is explicitly permitted; external-model-generated CoT + public HF datasets appear allowed and were used by competitors without apparent DQ. Hard constraint = rank≤32 LoRA, real training (no weight repack). External-teacher CoT (andy279) is a *different compliance posture* than our prior own-work CoT — get explicit human OK before relying on it.

## Chosen directions

| # | Account | Direction | Why | Compliance | Cost |
|---|---|---|---|---|---|
| **A** | harrysun2006 | **Spectral/SVD surgery on the 0.86 soup** (`nemo-surgery-a`) — sweep global-scale + top-energy-amplify (incl. lopure's e=0.844) + Mamba-only configs; score each on the fixed hard-val with the official metric; package the best-beating-soup variant. | Highest-confidence path to 0.87–0.89 (lopure precedent + Spectral Surgery). Post-hoc, **no training**, ~1–2h, rank-preserving. | ✅ own-work transform of our own adapter | cheap |
| **B** | firefly2006 | **Solver-guided bit/equation teacher-CoT adapter** (andy279 subset) — fresh v14-recipe LoRA + the ~2,703 solver-guided hard-cat traces; submit standalone and/or soup with v14. Attacks the only unsolved frontier (`equation`). | Highest *ceiling* — the documented 0.85→0.87 lever; orthogonal to A. | ⚠ external-teacher CoT — **needs human OK on rules** | ~7h + 1 may slot |

Deliberately NOT pursued: another v11 stage-2 SFT (T5 — cipher-heavy + self-distillation saturation), generic merge-search (capped, dilutive per T12).

## Status (updated 2026-06-15 ~13:00 UTC)
- **A — `harrysun2006/nemo-surgery-a` (running, healthy).** Past env + surgery→save→vLLM-load preflight (~18 min RUNNING). Emits a hard-val ranking + the best-beating-soup `submission.zip` only (never regresses 0.86).
- **B split across may's slots (human-authorized both):**
  - **`firefly2006/nemo-v11-sft-d` (running).** Compliant own-work SFT on may's v11-sample-b verified corpus (261 CoTs). Low-EV (T12 + self-distillation saturation) but uses a slot.
  - **`firefly2006/nemo-andy279-prep` (COMPLETE) + `nemo-andy279-train` (running).** The andy279 HF dataset is gated; unblocked with an HF read token embedded only in the private Kaggle prep kernel (repo copy keeps `_HF_TOKEN` empty + Kaggle-Secret/env fallback). Prep emitted **34,522** frontier teacher CoTs (bit 17,275 / equation 10,525 / cipher 6,722; solver-guided "find the rule" style). Train weaves a per-category-capped subset (equation 800 / bit 600 / cipher 300) into the v14 replay recipe → fresh rank-32 LoRA. No harry↔may *adapter* sharing needed (both may directions train fresh on the public v14 recipe). ⚠ Rotate the HF token after close.
- Submissions to the leaderboard remain gated on explicit human approval (CLAUDE.md).
