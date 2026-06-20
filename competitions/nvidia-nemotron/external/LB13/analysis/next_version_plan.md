# Next-version plan — `lb13-v1`

> Post-competition plan derived from the **13th Place Solution** (teacher oracle 89.4%).
> **Status: PLAN ONLY.** No GPU training, no Kaggle submit, no kernel push, no dataset upload now
> (`allow_* = false`; competition ended). Anchors: `gap_analysis.md`, `score_tricks.md`, `method_summary.md`, `../writeup/lb13-writeup.md`.

## Version name
`lb13-v1`

## Hypothesis
The highest-value borrow is the **equation_numeric structural model** (4 mutually-exclusive operator categories + exclusivity + **reversal symmetry shared across all examples** + majority-vote global reversal), which gives LB13 the **highest guess rate in the batch (50.7%)** and 95.3% deduce — refuting our equation-cipher premise. Second: **keep & rebalance teacher-incorrect traces 1:1** (LB13 + LB10 both show excluding failures hurts), challenging our c1/c2 verified-only filter. Third: **bit 3-input verification (MAJ/XNOR)** and a **3-stage decreasing-LR SFT** for trace-fidelity.

## What we borrow from LB13
- **equation solver**: category exclusivity, reversal symmetry (both-in-out-or-neither, shared across examples), global reversal by majority vote; deduce via target-operator examples; guess by strict family exclusion (ties sub>add>mul>concat).
- **Data**: keep teacher-incorrect traces; **rebalance correct:incorrect = 1:1**; robust aggregation (match ≥1 example); augment cryptarithm from equation seeds.
- **bit**: 3-input verification (MAJORITY/XNOR), bit-position-restricted search, left-edge fallback, drop parsing-display to free tokens.
- **SFT**: **3 stages with decreasing LR** (2e-4 linear → 2e-5 cosine → 5e-6 cosine, upsample bit+cryptarithm last); aggressive/overfit-prone for CoT fidelity; targets without lm_head.
- Output hygiene: de-brace cryptarithm answers.

## What new ideas we add (beyond LB13)
- **A/B keep-failures vs verified-only** on our data, with LB13's 1:1 rebalance (combine with LB10's finding).
- **Graft cryptarithm** from LB1 (signature catalog) / LB3 (CSP + two-stage) — LB13 cryptarithm is only 10%.
- **Equation-deduce re-crack (no GPU)** using LB13's symmetry+exclusivity model — shared with `lb{1,3,5,6,10}-v1`; this is the most actionable equation structure across all writeups.

## Data / corpus plan
- Improved per-category reasoners (raise teacher oracle). Keep incorrect traces; rebalance 1:1; robust aggregation; cryptarithm 3× via equation seeds. No weights/large data in git.

## Prompt format
- Competition templates; de-braced cryptarithm output; trim bit parsing-display to free token budget for verification.

## Solver / synthetic generation plan
1. `equation_solver.py`: category exclusivity + reversal symmetry + majority-vote reversal + family-exclusion guess.
2. `bit_3input_verify.py`: MAJ/XNOR verification + bit-position-restricted search + left-edge fallback.
3. `rebalance.py`: 1:1 correct:incorrect; robust aggregation (≥1-example match); cryptarithm-from-equation augmentation.

## Training config (when GPU authorized — NOT now)
- Base Nemotron-3-Nano-30B; LoRA rank/alpha 32/32, dropout 0; targets q/k/v/o + in/out + up/down (no lm_head).
- **3-stage**: (1) 2ep LR 2e-4 linear; (2) 1ep LR 2e-5 cosine; (3) 1ep LR 5e-6 cosine, upsample hard cats. Eff batch 32, AdamW.
- **Down-scale for post-comp RTX Pro 6000**: the 3-stage schedule on a reduced corpus ≈ **8-16h**. Validate the *mechanism* (equation structure lift, keep-failures A/B, 3-stage gains), not full coverage.

## Validation plan (incl. T12 hard-val)
- **Primary**: per-category teacher oracle (the optimization target) + a held-out official-metric set; equation guess/deduce solved-fraction.
- **Secondary**: T12 hard-val (hard-tail hint; INS-002).
- Verify the 1:1-rebalance and 3-stage changes don't regress easy categories.

## Local official-like metric / extraction checks
- `\boxed{}` exact / rel-1e-2; per-category teacher oracle; equation symmetry/family-assignment self-consistency.

## Submit / no-submit gate
- **Competition over → no live submission; gate N/A now.** Future live: select by validation/oracle, not public; ship the trace-fidelity-best run.

## Expected upside
- Equation toward ~95% deduce / ~50% guess (the batch's best equation structure). Bit toward ~90% via 3-input verification. cryptarithm needs LB1/LB3 grafts. Realistically post-comp we validate the **mechanism** (equation structure, keep-failures A/B, 3-stage SFT).

## Risks
- **cryptarithm** stays low without a real solver (10%).
- **Equation premise** (decisively refuted ×6) — re-test is cheap and high-value.
- **Keep-failures A/B** may not replicate on our pipeline; 1:1 rebalance ratio may need tuning.
- **3-stage SFT** adds run-management overhead.

## GPU time estimate (for a future authorized run)
- LB13 reference: 3-stage SFT, Unsloth (Kaggle-class), eff batch 32. Our down-scaled validation ≈ **8-16h** on the RTX Pro 6000. Reasoner/data prep: CPU, hours.

## Implementation checklist
- [ ] No-GPU: equation-deduce re-crack with LB13's symmetry+exclusivity model (shared with `lb{1,3,5,6,10}-v1`).
- [ ] Build `equation_solver.py` (symmetry + exclusivity + majority-vote reversal + family-exclusion guess).
- [ ] Build `bit_3input_verify.py` (MAJ/XNOR + bit-position search + left-edge fallback).
- [ ] Build `rebalance.py` (1:1 correct:incorrect, robust ≥1-example aggregation, cryptarithm-from-equation).
- [ ] A/B keep-failures vs verified-only (our c1/c2).
- [ ] (GPU-gated) 3-stage decreasing-LR SFT, down-scaled; record under `runs/`.
- [ ] Per-category oracle + held-out eval; check no easy-cat regression.

## Rollback / hold-best strategy
- **Hold-best = our soup (Public 0.86 / Private 0.85)** + post-deadline **eq-aug (0.86/0.86)**. Any `lb13-v1` artifact must beat these on the offline metric before consideration; on regression, **revert to held-best** and keep `lb13-v1` as a documented method experiment. All work on a branch / under `runs/`; no held-best overwrite; no force-push.
