# Next-version plan — borrowing from LB80 (post-Saturday GPU reset)

> Analysis/planning only (no GPU/submit/push in this task). Synthesises the LB80 gap analysis with our
> `research.md §4` GRPO design + the `tasks.md` EQ-4 RLVR task. Borrows are from untrusted competitor
> writeups — verify before trusting. RL at 30B likely needs external GPU (#83), not just the RTX PRO 6000.

## Version name
**v17-grpo** — "dense-reward GRPO on the SFT prior" (break the 0.86 SFT ceiling on bit).

## Hypothesis
SFT plateaus at 0.86 because the answer-level reward is **sparse** (a near-correct 8-bit answer scores 0,
gradient vanishes on the hardest rows). **GRPO with a DENSE per-step verifiable reward** (column layout +
operation choice + per-bit correctness + final-answer verify) + a **superlinear all-correct ("champagne")
bonus**, initialized from our strong SFT prior, gives gradient on partial correctness and pushes **bit** (and
secondarily cipher) past where SFT saturates — the LB80 lever. Equation stays bounded (no usable per-step verifier).

## What we borrow from LB80
1. **Two-stage SFT→GRPO** — RL on top of a competent SFT prior (not from base).
2. **Dense per-step verifiable reward** — partial credit at each trace step, not terminal 0/1.
3. **Superlinear "champagne" bonus** — flat +N for a fully-correct answer, to shape toward completion.
4. (Alt, cheap) **adapter singular-value amplification** (lopure ~0.89) — a no-RL fallback to test first.

## What we add (ours, validated)
- Initialize GRPO from the **v14 (0.85) or the 0.86 soup** adapter (strong prior; cold-start GRPO is unstable).
- Reuse our **`eval/official_metric.verify`** as the terminal correctness check inside the reward (exact / 1e-2).
- **Soup the RL survivor** into v14+c1+b1 as a new comparable+complementary member (INS-004) — orthogonal to RL.
- Keep **eq-aug** standalone for equation (RL won't help the cipher tail).

## Data / corpus plan
- RL prompts: **bit-manipulation** train rows first (cleanest verifier), curriculum solver-solvable →
  solver-unsolvable; then a small cipher set. Few hundred prompts to start (cost control).
- Optional stronger cold-start: solver-guided teacher CoT (andy279-style) for bit — own-solver rule + teacher
  trace (⚠ verify competition/data rules permit external-model traces; our prior andy279 SFT *regressed* at
  high dose, so use only as RL cold-start, low dose).

## Prompt format
Eval-faithful (chat template + `\boxed{}` SUFFIX). Reward parses the trace for: output-column layout, declared
operation, per-bit answer, and a final `verify(gold, extract_final_answer)` that **must dominate** (anti-reward-hack).

## Training config
- **Algorithm:** GRPO (group-relative, no value net), rank-32 LoRA, group size G=4–8 rollouts/prompt.
- **Reward** = Σ small per-step terms (layout/op/per-bit/VER) + **+N champagne** if `verify`==True; clamp so a
  wrong final answer can never out-score a correct one. Format term for a single well-formed `\boxed{}`;
  length penalty under the 7,680 cap.
- **Backend:** NeMo-RL (or TRL GRPO) — likely **external GPU (#83)**; 30B online rollouts exceed Kaggle kernels.
- Start tiny: few hundred bit prompts, short rollout cap, few hundred steps; expand only if the local metric moves.

## Validation plan (incl. T12 hard-val) — gate BEFORE any submit
1. Local `eval/official_metric` on `eval/hard_val_ids.json` (greedy 7680/temp 0, exact-or-1e-2), per category.
2. **Require bit hard-val ↑ vs the SFT prior with no regression on cipher/numeral/gravity/unit** (the dense
   reward must not break easy categories — watch for reward-hacking / format drift).
3. Reward-curve sanity: mean reward rising, champagne-rate rising, output length stable (no runaway CoT).
4. Compare to soup/v14 0.764 hard-val baseline.

## Submit / no-submit gate
- Submit only if local hard-val beats the SFT prior (esp. bit) with no easy-category regression.
- **Late-window submission needs explicit human approval** (this task is analysis-only; submission is future).
- Soup-grow the GRPO adapter into v14+c1+b1 only if it lifts the local metric.

## Risks
- **Cost/instability:** 30B online GRPO is heavy + can collapse; mitigate with strong SFT init, tiny start,
  bounded rollouts; likely needs external GPU (#83), not just the RTX PRO 6000.
- **Reward hacking:** dense partial credit can be gamed without solving — the final `verify` term must dominate;
  audit sampled traces.
- **Equation won't move:** no usable per-step verifier for the strong cipher — don't target it with RL.
- **Compute > Saturday quota:** if external GPU isn't available, fall back to the **cheap no-RL lever first**
  (adapter singular-value amplification on the soup, gated on T12) — see `v16-mlp` (LB25 plan) as the SFT-side companion.

## GPU estimate
- Adapter-surgery fallback: **~0 GPU** (CPU SVD edit) + local eval — do this first.
- GRPO proper: **several GPU sessions** of online rollouts (external, #83); not a single RTX PRO 6000 run.
  Budget ≈ 2–4 sessions for a small bit-only pilot.

## Implementation checklist
- [ ] (cheap first) adapter singular-value amplification on the 0.86 soup → T12 gate
- [ ] dense per-step reward fn (layout/op/per-bit/VER + champagne) with `verify` dominating
- [ ] GRPO harness (NeMo-RL / TRL), rank-32 LoRA, init from v14/soup, G=4–8
- [ ] bit-only pilot: few hundred prompts, bounded rollout, few hundred steps
- [ ] local `eval/official_metric` on hard_val_ids; reward-curve + trace audit
- [ ] gate: bit hard-val ↑, no easy-cat regression → request human approval → submit
- [ ] soup-grow the survivor into v14+c1+b1 if local metric improves
- [ ] secure external GPU (#83) before scaling beyond the pilot
