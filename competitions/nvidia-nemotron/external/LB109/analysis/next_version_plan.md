# Next-version plan — `lb109-v1`

> Derived from the **109th Place "Heuristics" writeup** (final ~0.82; mostly ideas).
> **Status: PLAN ONLY.** No GPU training, submit, kernel push, or dataset upload (`allow_* = false`; comp ended). Anchors: `gap_analysis.md`, `score_tricks.md`, `method_summary.md`, `../writeup/lb109-writeup.md`.

## Version name
`lb109-v1`

## Hypothesis
Two LB109 ideas are concrete accelerators for our hard-category solvers: the **ANF (algebraic normal form) trick** shrinks the 3-arg bit search to 2-arg table matching, and **modular branch-cutting** (mod 10/37/11/100) lets a deterministic cryptarithm search converge within the 7k-token budget. The **equation/cryptarithm guess sign-deduction (unused/opposite)** corroborates (8th time) that these categories are inferable. The meta-lesson: **ship partial wins** (XOR3, mod-10) rather than chase a perfect solver.

## What we borrow from LB109
- **bit ANF trick:** partial-ANF for XOR/OR/XOR_OR/Choice/Maj/OR_XNOR; XOR on output; match precomputed tables. Negation canonicalization (`Shift(Not(x))`).
- **cryptarithm modular branch-cutting:** mod-10 carry constraints; mod 37 (<5000 combos), mod 11 (palindromes), mod 100 (multiplication); branch on the smallest set; 13k-symbol / 7k-token cap.
- **operator-class constraints + guess sign-deduction** (unused/opposite).
- **process discipline:** ship partial wins; **score candidates by length + information gain** for token-budget pruning.

## What new ideas we add
- Combine the ANF trick + modular pruning with LB1/LB3 cryptarithm structure and LB10's key-table bit reasoner.
- Equation-deduce/guess re-crack (no GPU) using the sign-deduction — shared with `lb{1,3,5,6,10,13}-v1`.
- A CV gate to catch the cryptarithm overfit LB109 hit (0.82).

## Data / corpus, training, validation
- Implement the ANF bit investigator + modular cryptarithm investigator; emit compact CoTs (score candidates by length+info-gain to fit 7k tokens). Validate with category-stratified + hard-val (official extractor); a CV gate prevents the rushed-cryptarithm overfit. Down-scaled RTX Pro 6000 run ≈ 6-12h to validate the mechanisms.

## Submit / no-submit gate, risks, rollback
- Comp over → gate N/A. Risks: ANF `xyz` term handling on edges; modular pruning correctness; CoT still too long; overfit if cryptarithm data is rushed (LB109's lesson). **Hold-best = soup (0.86/0.85) + eq-aug (0.86/0.86); revert on regression.** All on a branch / under `runs/`; no held-best overwrite; no force-push.

## Implementation checklist
- [ ] No-GPU: equation guess/deduce re-crack with sign-deduction (shared).
- [ ] Bit ANF investigator (partial-ANF + XOR-on-output matching) + negation canonicalization.
- [ ] Cryptarithm modular branch-cutting (mod 10/37/11/100) on top of a class-constrained search.
- [ ] Candidate scoring by length + info-gain (token-budget pruning).
- [ ] CV gate to catch hard-cat overfit.
- [ ] (GPU-gated) down-scaled run; category-stratified + hard-val; no easy-cat regression.

## GPU time estimate
- LB109 was mostly CPU heuristic dev + one rushed training (0.82). Our down-scaled validation ≈ **6-12h** on the RTX Pro 6000. Investigator dev: CPU, hours.
