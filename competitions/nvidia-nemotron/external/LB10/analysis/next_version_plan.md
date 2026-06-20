# Next-version plan — `lb10-v1`

> Post-competition plan derived from the **10th Place Solution** (Public 0.860 / Private 0.880).
> **Status: PLAN ONLY.** No GPU training, no Kaggle submit, no kernel push, no dataset upload now
> (`allow_* = false`; competition ended). Anchors: `gap_analysis.md`, `score_tricks.md`, `method_summary.md`, `../writeup/lb10-writeup.md`.

## Version name
`lb10-v1`

## Hypothesis
Most of our headroom is in the **deterministic teacher**, not SFT tuning: matching the bit reasoner to the true generator (a **rotate/shift key-table**) and adding **oracle-ceiling-vs-fidelity + logprob learnability** diagnosis will lift bit toward ~98% and make our imitation gaps visible. Two LB10 results directly challenge our practice and are worth A/B testing: **keeping failed/low-confidence traces** (LB10: excluding them hurt) and **not relying on LoRA merge** (LB10: merge failed). Plus the equation-deduce premise re-test (5th refutation).

## What we borrow from LB10
- **"Improve the teacher" discipline** — measure and raise per-category **oracle coverage** first; treat it as the score ceiling.
- **Rotate/shift key-table bit reasoner**: `out[i]=F(rotl(x,a),shl(x,b),shr(x,c))`, F read from examples as a 3-bit-key→bit table; recover `(a,b,c)` from boundary bits (bit0 shr=0, bit7 shl=0); compact `key>value` traces; gate extra scans by a threshold.
- **equation**: deduce candidate reorder by frequency; guess two-axis rebuild (operation = conventional-if-free else first-unused of {add, unsigned abs-diff, mul}; wrapper pinned from the most-example seen operator).
- **Validation**: 950 held-out per category; **oracle-ceiling vs model-fidelity** split; **per-example/per-epoch logprob learnability**; **select by validation, not public LB**.
- **Training**: alpha/r=4; priority 2× for fragile modes; add low-logprob problems + failure-mode demos and retrain.
- **Keep failed / low-confidence (`rule_unknown`) traces** (don't filter to solver-correct only).

## What new ideas we add (beyond LB10)
- **A/B our c1/c2 verified-only filter vs LB10's keep-failures** on our data — settle whether our filter discards useful signal.
- **A/B LoRA merge** under LB10's negative result vs our +0.01 and LB5's iterative soup — characterize when soup helps (member complementarity, averaging target).
- **Graft cryptarithm** from LB1 (signature catalog) / LB3 (CSP + two-stage) — LB10's cryptarithm is only 9% (add/sub/mul too jumpy); the top-end lever is a real cryptarithm solver.
- **Equation-deduce re-crack (no GPU)** — shared with `lb{1,3,5,6}-v1`.

## Data / corpus plan
- Program-generated deterministic traces per category; prompt-masked; >8192-token filter. Keep failed/low-conf traces (tagged `rule_unknown`). Priority 2× fragile modes; add low-logprob problems. No weights/large data in git.

## Prompt format
- Compact deterministic CoT ending `\boxed{}`; remove per-example echoes + candidate enumeration to avoid runaway loops; `key>value` rendering.

## Solver / synthetic generation plan
1. `bit_keytable_reasoner.py`: rotate/shift key-table; boundary-bit (a,b,c) recovery; conflict-pruned key-table accumulation; agreement/majority fallback; compact traces.
2. `equation_solver.py`: frequency-ordered deduce; two-axis guess; wrapper pinning.
3. `gen_*.py`: per-category generators; keep failed/low-conf traces.
4. `learnability.py`: per-example/per-epoch logprob export to find fragile traces.

## Training config (when GPU authorized — NOT now)
- Base Nemotron-3-Nano-30B; LoRA rank 32 / **alpha 128 (alpha/r=4)**; all-proj + lm_head; LR 2e-4 linear; **2 epochs**; eff batch 32; stratified.
- **Down-scale for post-comp RTX Pro 6000**: a few-category run validating the **bit key-table oracle lift** + the **keep-failures A/B** + **merge A/B** ≈ **8-16h**. Validate the *mechanism*, not full coverage.

## Validation plan (incl. T12 hard-val)
- **Primary**: 950 held-out per category; **oracle-ceiling vs model-fidelity** split; logprob learnability.
- **Secondary**: T12 hard-val (hard-tail hint; INS-002).
- **Select by validation**, never public; check cross-category regressions per change.

## Local official-like metric / extraction checks
- `\boxed{}` exact / rel-1e-2; "correct within 7680/8192 tokens"; per-category oracle coverage + model-vs-oracle fidelity; logprob histograms.

## Submit / no-submit gate
- **Competition over → no live submission; gate N/A now.** Future live: select by validation; ship the higher-validation run even if public is lower (LB10's lesson).

## Expected upside
- Bit toward ~98% (key-table). Equation toward ~93% deduce. Diagnosis (oracle vs fidelity, logprob) unblocks targeted fixes. Cryptarithm needs LB1/LB3 grafts. Realistically post-comp we validate the **mechanism** (bit key-table lift, keep-failures A/B, merge A/B), not full coverage.

## Risks
- **Cryptarithm** stays low without a real solver (LB10 = 9%).
- **Equation premise** (unlikely to hold after 5 refutations) — cheap to check.
- **Keep-failures A/B** may not replicate on our data/pipeline.
- **Merge A/B** is confounded (member complementarity); design carefully.
- **Compute** for the full teacher rebuild.

## GPU time estimate (for a future authorized run)
- LB10 reference: single base model, LoRA, 2 epochs, eff batch 32 (Kaggle-class). Our down-scaled validation ≈ **8-16h** on the RTX Pro 6000. Reasoner/generation prep: CPU, hours.

## Implementation checklist
- [ ] No-GPU: equation-deduce re-crack (shared with `lb{1,3,5,6}-v1`).
- [ ] Build `bit_keytable_reasoner.py` (boundary-bit recovery) + measure oracle lift.
- [ ] Build `equation_solver.py` (frequency-order deduce + two-axis guess).
- [ ] Build `learnability.py` (logprob export) + oracle-vs-fidelity reporting.
- [ ] A/B keep-failures vs verified-only (our c1/c2).
- [ ] A/B LoRA merge (characterize when soup helps).
- [ ] (GPU-gated) down-scaled run (alpha/r=4, 2 epochs); record under `runs/`.
- [ ] Select by validation; check per-category regressions.

## Rollback / hold-best strategy
- **Hold-best = our soup (Public 0.86 / Private 0.85)** + post-deadline **eq-aug (0.86/0.86)**. Any `lb10-v1` artifact must beat these on the offline metric before consideration; on regression, **revert to held-best** and keep `lb10-v1` as a documented method experiment. All work on a branch / under `runs/`; no held-best overwrite; no force-push.
