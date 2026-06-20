# Next-version plan — `lb88-v1`

> Derived from the **88th Place Solution** (= LB92; see `../LB92/analysis/next_version_plan.md` for the prior `v18-stable` plan).
> **Status: PLAN ONLY.** No GPU training, submit, kernel push, or dataset upload (`allow_* = false`; comp ended).

## Version name
`lb88-v1` (≈ LB92's `v18-stable`)

## Hypothesis
Our "synthetic dilutes" failure is fixable with **statistics-matched synthetic + a synthetic-vs-original gap QC loop** (final ~2.5:1), and symbol-category learning is unblocked by **per-character tokenization**; **grad-clip 1.5** tames submission variance. None require solving cryptarithm/bit harder.

## What we borrow from LB88/LB92
- Statistics-matched generator (char freq, numeric ranges, transform distributions) + **synthetic-vs-original eval-gap QC** to iteratively fix the generator; ramp toward **2.5:1 synth:original** only if QC + hard-val hold.
- **Per-character tokenization** (synthetic tokens) for equation/cipher/cryptarithm.
- **Gradient clipping 1.5** (A/B vs our 1e9-off; watch run-to-run variance).
- **Protect already-solvable categories** (= our T12 anti-dilution).

## What new ideas we add
- Combine with LB1/LB3 cryptarithm structure (LB88 deliberately didn't attack it).
- Equation-deduce re-crack (no GPU) — shared with `lb{1,3,5,6,10,13}-v1`.

## Data / corpus, training, validation
- Statistics-matched synth + gap QC; per-char tokens; grad-clip 1.5; Unsloth/CCE. Validate with **category-stratified + hard-val** scored by the official extractor; gate on T12 ≥ 0.764 + no easy-cat regression. Down-scaled RTX Pro 6000 run ≈ 6-12h to validate the mechanism.

## Submit / no-submit gate, risks, rollback
- Comp over → gate N/A. Risks: per-char tokens may interact with the base tokenizer; grad-clip A/B confounded by other changes; generator fidelity. **Hold-best = soup (0.86/0.85) + eq-aug (0.86/0.86); revert on regression.** All on a branch / under `runs/`; no held-best overwrite; no force-push.

## Implementation checklist
- [ ] No-GPU: equation-deduce re-crack (shared).
- [ ] Statistics-matched generator + synthetic-vs-original gap QC.
- [ ] Per-character tokenization for symbol categories.
- [ ] grad-clip 1.5 A/B (variance check).
- [ ] (GPU-gated) down-scaled run; T12 + category-stratified eval; no easy-cat regression.

(Full detail in `../LB92/analysis/next_version_plan.md`.)
