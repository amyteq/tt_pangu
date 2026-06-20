# Next-version plan — `lb6-v1`

> Post-competition plan derived from the **6th Place (2nd public) Solution**.
> **Status: PLAN ONLY.** No GPU training, no Kaggle submit, no kernel push, no dataset upload now
> (`allow_* = false`; competition ended). Anchors: `gap_analysis.md`, `score_tricks.md`, `method_summary.md`, `../writeup/lb6-writeup.md`.

## Version name
`lb6-v1`

## Hypothesis
The largest cheap win from LB6 for us is **attribution + validation**: a **per-domain LB-probing (DUMMY-masking) harness** plus **full-train-as-validation** would have let us isolate which category each change helps/hurts — directly addressing our recurring B8 ("single-category gain ≠ total gain"). On capability: a **template bit solver (hex + monotonic skips)** and a **DFS cryptarithm/equation solver with reversed search** close the hard-category gap, and the equation-deduce premise must be re-tested (4th refutation).

## What we borrow from LB6
- **Per-domain probing via DUMMY masking**: train the model to output `I will ignore this problem\n\boxed{DUMMY}` for all non-target domains → isolate one domain's signal (on the public LB historically; for us, on a local/offline set since the comp is over).
- **Full-train-as-validation** with distribution-matched synthetic.
- **Template bit solver**: shl/shr/rotr + pairwise (XOR/AND/OR/NOT) + ternary (MAJ/CH); iterate shifts; **monotonic skips**; **hex arithmetic + hex cheatsheet**.
- **DFS cryptarithm/equation solver**: tree search over mapped equations (add/sub/mul families + maxmodmin); **reversed search**; op-deduction / leading-zero / leading-one / equation-sorting pruning.
- **Data discipline**: distribution-matched synthetic; **over-weight bit** (it's fragile to mix changes); **targeted hallucination subsets**; reroll cryptarithm digit maps until solvable under budget.

## What new ideas we add (beyond LB6)
- **Offline DUMMY probing** (comp is over): run the masking trick against our local official-metric set + T12, not the public LB, to get per-domain attribution we can iterate on.
- **Combine with LB1/LB3/LB5**: LB6's plain DFS is weaker on cryptarithm than LB1's signature catalog / LB3's two-stage — graft those onto LB6's strong validation + bit templates.
- **Calibrate the bit/cryptarithm data trade-off** that cost LB6 2nd-3rd: build a CV that predicts the bit-CV drop when cryptarithm data is added (their estimate was off).
- **Equation-deduce re-crack (no GPU)** — shared with `lb{1,3,5}-v1`.

## Data / corpus plan
- Distribution-matched synthetic per domain (example-count, parameter distributions, cipher structure, bit per-template variation with more 3-atom problems, cryptarithm reroll-until-solvable).
- **bit ≈ 65-70% of tokens** (LB6's fragility finding); protect easy 100% categories; targeted hallucination subsets.
- Full train.csv reserved for validation (don't train on it). No weights/large data in git (→ object storage / `artifacts/`).

## Prompt format
- Competition templates; algorithmic CoT; **DUMMY output** (`I will ignore this problem\n\boxed{DUMMY}`) for masked domains during probing. Hex arithmetic only after a tokenizer check (LB5 caution).

## Solver / synthetic generation plan
1. `bit_template_solver.py`: template set + shift iteration + monotonic skips + hex CoT + hex cheatsheet.
2. `cryptarithm_dfs.py`: tree search (families + maxmodmin) + reversed search + op-deduction/leading-zero/leading-one/equation-sorting.
3. `equation_solver.py`: same, digits known.
4. `gen_*.py`: distribution-matched generators + targeted hallucination subsets; cryptarithm reroll-until-solvable.
5. `dummy_probe.py`: assemble DUMMY-masked datasets per target domain for attribution.

## Training config (when GPU authorized — NOT now)
- Base Nemotron-3-Nano-30B; Unsloth; **BS 32, LR 3.5e-4** (A/B vs our v14 LR), rank32/α32, 1 epoch. Optionally Tinker for velocity.
- **Down-scale for post-comp RTX Pro 6000**: LB6 used ~0.25-0.5B tokens. A down-scaled run (~50-150M tokens) ≈ **6-14h** — validate the *mechanism* (DUMMY probing attribution, bit templates, DFS cryptarithm), not full volume.

## Validation plan (incl. T12 hard-val)
- **Primary**: full-train-as-validation with distribution-matched synthetic + **per-domain DUMMY probing** on a local official-metric set.
- **Secondary**: T12 hard-val (hard-tail hint; INS-002 caveat).
- Track **per-domain solved-problem counts** (LB6's `-0/-1/-2` style) and the **bit-CV sensitivity** to mix changes.

## Local official-like metric / extraction checks
- `\boxed{}` exact (strings) / rel-1e-2 (numerics); "correct within 7680 tokens"; per-domain solved counts; verify DUMMY masking produces a clean per-domain signal locally.

## Submit / no-submit gate
- **Competition over → no live submission; gate N/A now.** Future live: use per-domain LB probing for attribution; **calibrate the bit/cryptarithm trade-off** before committing a final dataset; ship a stability hedge (two seeds) only when CV is calibrated.

## Expected upside
- Attribution: per-domain signal unblocks targeted iteration (fixes B8). Bit toward ~92-94%; equation toward ~93%. Cryptarithm only ~17% with LB6's plain DFS (graft LB1/LB3 to go higher). Realistically post-comp we validate the **mechanism**, not the full 0.90.

## Risks
- **bit/cryptarithm zero-sum**: adding cryptarithm data hurts bit CV more than expected (LB6's regret) — calibrate first.
- **Equation premise**: if our global-cipher verdict holds (unlikely after 4 refutations), the re-test yields nothing (cheap).
- **Hex tokenization**: may break our model like LB5's encoding — validate first.
- **DUMMY probing offline**: the comp LB is gone; a local probe must be representative or attribution misleads.
- **Compute**: full pipeline is heavy; down-scaled may under-deliver.

## GPU time estimate (for a future authorized run)
- LB6 reference: ~0.25-0.5B tokens (Unsloth, Kaggle/GCP G4; Tinker late).
- Our down-scaled validation: ≈ **6-14h** on the RTX Pro 6000. Generation/probing prep: CPU, hours.

## Implementation checklist
- [ ] No-GPU: equation-deduce re-crack (shared with `lb{1,3,5}-v1`).
- [ ] Build `dummy_probe.py` + a local per-domain attribution harness.
- [ ] Build `bit_template_solver.py` (templates + skips + hex, after tokenizer check).
- [ ] Build `cryptarithm_dfs.py` (reversed search + pruning) and `equation_solver.py`.
- [ ] Distribution-matched generators + targeted hallucination subsets; bit over-weighting.
- [ ] CV that predicts bit-CV drop vs cryptarithm-data added (calibrate the trade-off).
- [ ] (GPU-gated) down-scaled run; record under `runs/`; per-domain solved counts.
- [ ] (If live) per-domain probing for attribution; else write up method-validation results.

## Rollback / hold-best strategy
- **Hold-best = our soup (Public 0.86 / Private 0.85)** + post-deadline **eq-aug (0.86/0.86)**. Any `lb6-v1` artifact must beat these on the offline metric before consideration; on regression, **revert to held-best** and keep `lb6-v1` as a documented method experiment. All work on a branch / under `runs/`; no held-best overwrite; no force-push.
