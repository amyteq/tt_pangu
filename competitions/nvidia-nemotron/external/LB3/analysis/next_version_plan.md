# Next-version plan — `lb3-v1`

> Post-competition plan derived from the **3rd Place Solution** (Private 0.900).
> **Status: PLAN ONLY.** No GPU training, no Kaggle submit, no kernel push, no dataset upload now
> (`allow_* = false`; competition ended). Reusable methodology for the next symbolic-reasoning competition
> and to close our postmortem loop. Anchors: `gap_analysis.md`, `score_tricks.md`, `method_summary.md`, `../writeup/lb3-writeup.md`.

## Version name
`lb3-v1`

## Hypothesis
Our 0.85→LB3 0.900 gap (~+0.05 private) is closable **without RL** primarily via (1) a **two-stage memorize→execute training** that makes the cryptarithm trace ~3× more sample-efficient, (2) a **CSP cryptarithm solver** (mul-pattern lookup + multi-example intersection + bounded backtracking), (3) **hex bit-trace compression** to free budget, and (4) a **leakage-controlled local validation that tracks the private LB** so we stop optimizing the noisy public 0.86 wall. Plus the equation-deduce premise re-test (LB3 independently shows equation_numeric_deduce ≈ 93% solvable).

## What we borrow from LB3 / 3rd Place
- **Two-stage training**: stage 1 = drill the lookup table (`<RECALL_DOMAINS>`/`<RECALL_ROWS>` completion, 16 packed per sample, request masked from loss); stage 2 = init from stage-1 adapter, train real traces + 3K retained drills.
- **CSP cryptarithm solver**: identify MUL examples → emit per-symbol domains + candidate mappings from a lookup table → **intersect/join** across MUL examples → anchor mappings → **bounded backtracking** (≤2 unknowns/eq, least-unknowns-first; non-neg vs neg op sets); (structure ∈ simple/reverse) × (mul ∈ a*b/a*b±1), reverse-first, early stop.
- **Bit**: hex + literal tail-2-bits compression; MAJ search; OR-NOT-first ordering.
- **Numeric**: minimal 13-op set; global simple/reverse; **operation-family** guessing for unseen operators.
- **Validation**: 10% stratified hold-out, exclude val rows AND val-derived augments; **perfect-trace-rate**; single-category isolation.
- **Modeling A/Bs**: MoE tie weights OFF; small effective batch (4); manual LM-head LoRA; CCE loop.
- **Augment by resampling originals** (don't free-generate).

## What new ideas we add (beyond LB3)
- **Combine LB1 + LB3**: LB1's fuller signature catalog (all 22 rules) as an *optional* stage-1 memory target, vs LB3's mul-only lookup — A/B which memory scope is most sample-efficient.
- **Soup on top** (our validated +0.01 lever) of a two-stage adapter — likely dominated by the method, but cheap to check.
- **Equation deduce re-crack** (no GPU): implement LB3's 13-op per-prompt solver on our `train.csv` to measure deduce solvability directly and retire/confirm our "global cipher" verdict.
- **Drill-as-regularizer ablation**: measure whether the 3K stage-2 drill injection is necessary for memory retention on our data.

## Data / corpus plan
- Keep the clean replay backbone; do **not** dilute (our b1/b2/v15 lesson).
- Build a **stage-1 drill corpus** covering all (mul-)signatures from the lookup table; 16 requests/sample, masked.
- Augment by **resampling originals**: cryptarithm to ~40–48K (the heavy lifter), bit 3K swap + 3K formula (×2), cipher 3K, numeric 3K. Exclude any augment derived from a validation original.
- Log token counts; protect the easy 100% categories.
- No weights/checkpoints/large data in git (artifacts → object storage / `artifacts/`).

## Prompt format
- Competition templates verbatim. Trace = staged procedure with explicit **`<RECALL_DOMAINS>`/`<RECALL_ROWS>` memory tags** + Q/C/S/N/Y solver notation; finality `</think>\boxed{...}` at the tail.

## Solver / synthetic generation plan
1. `mul_pattern_lookup.py`: build the signature→{domains, rows} table for multiplication types (R*, a*b±1); cap 48 rows/signature.
2. `cryptarithm_csp.py`: MUL identification → domain emission → intersection/join → anchor (≤8) → bounded backtracking (≤2 unknowns); emit the staged trace with `<RECALL_*>` tags.
3. `bit_hex_trace.py`: hex + tail-2-bit columns; add MAJ; OR-NOT-first ordering.
4. `numeric_solver.py`: 13-op minimal set; global simple/reverse; family-based guessing.
5. Stage-1 drill generator (packed, masked). Augmenters that resample originals with leakage exclusion.

## Training config (when GPU authorized — NOT now)
- Base Nemotron-3-Nano-30B; LoRA rank 32/α32, dropout 0, fp32, targets all-proj + lm_head (manual LM-head LoRA), **MoE tie OFF** (A/B vs our v14 tying).
- CCE loop; **effective batch size 4** (A/B vs 8/16); LR 2e-4 linear; grad norm 10; seq 8192; seed 42; 1 epoch.
- **Two-stage**: stage 1 (drills, eff batch 8) then stage 2 (real traces + 3K drills) from the stage-1 adapter.
- **Down-scale for the post-comp RTX Pro 6000**: full LB3 ≈ 58 GPU-h; a down-scaled validation (stage-1 on a signature subset + stage-2 on ~20–30K cryptarithm) ≈ **10–20h** — validate the *method* (sample efficiency, recall quality), not LB3's volume.

## Validation plan (incl. T12 hard-val)
- **Primary**: 10% stratified hold-out scored with the official extractor; verify it correlates with our known LB points (build the private-tracking property).
- **Secondary**: T12 hard-val (existing) as a hard-tail hint only (INS-002 caveat).
- **Trace fidelity**: perfect-trace-rate (>85% bit, >95% cipher/numeric); cryptarithm recall/self-consistency.
- Guard against the dilution regression; single-category isolation for each change.

## Local official-like metric / extraction checks
- `\boxed{}` exact (strings) / rel-1e-2 (numerics); "correct within 7680 tokens" rule; per-category accuracy; token-length histograms (bit median target reduced via hex).

## Submit / no-submit gate
- **Competition over → no live submission; gate N/A now.** For a future live run: select on the **private-tracking offline metric**, not the public LB; submit only if it beats held-best offline without easy-cat regression; respect quota.

## Expected upside
- Cryptarithm: the two-stage + CSP path is the largest single lever (LB3 local cryptarithm_deduce 30.3%, but the method is what moved private to 0.900). Bit toward ~89% category (LB3). Realistically post-comp we validate the **mechanism** (two-stage sample efficiency, hex token savings, equation-deduce solvability), not the full 0.900.

## Risks
- **Compute**: 58 GPU-h full; down-scaled run may under-deliver and confound "method works" with "not enough data."
- **Equation premise**: if our global-cipher verdict is right for deduce too, the re-test yields nothing (cheap to check first).
- **Two-stage complexity**: stage-1 memory may not transfer on our trace format; mitigate with the drill-injection retention trick.
- **Catalog/lookup reproduction**: LB3 code unreleased (the example trace is an attachment we don't have); rebuild from prose; solve-rate numbers (24.2%, deduce 27.8%) are sanity checks.
- **MoE-tie-off conflicts with our v14 tying** — treat as an explicit A/B, not a drop-in.

## GPU time estimate (for a future authorized run)
- LB3 reference: stage-1 25.2h + stage-2 32.7h ≈ 58h (single GPU, ~4.6×10^8 tokens). Lookup/drill generation: CPU, hours.
- Our down-scaled validation: ≈ **10–20h** on the RTX Pro 6000. Eval sweeps: a few GPU-hours.

## Implementation checklist
- [ ] No-GPU: equation-deduce re-crack with a 13-op per-prompt solver on `train.csv` (settle the premise; shared with `lb1-v1`).
- [ ] Build `mul_pattern_lookup.py` (+ verify row caps).
- [ ] Build `cryptarithm_csp.py` (intersection/anchor/backtracking) emitting `<RECALL_*>`-tagged traces.
- [ ] Build `bit_hex_trace.py` (hex+tail bits, MAJ, OR-NOT-first).
- [ ] Build `numeric_solver.py` (13-op, family guessing).
- [ ] Stage-1 drill generator (packed/masked) + leakage-aware augmenters.
- [ ] Build the **private-tracking** 10% stratified validation + perfect-trace-rate metric.
- [ ] (GPU-gated) two-stage SFT down-scaled; record under `runs/`.
- [ ] Eval: per-category + trace-fidelity; no easy-cat regression.
- [ ] (If live) select on offline metric; else write up method-validation results.

## Rollback / hold-best strategy
- **Hold-best = our soup (Public 0.86 / Private 0.85)** + post-deadline **eq-aug (0.86/0.86)**. Any `lb3-v1` artifact must beat these on the offline metric before consideration; on regression, **revert to held-best** and keep `lb3-v1` as a documented method experiment. All work on a branch / under `runs/`; no held-best overwrite; no force-push.
