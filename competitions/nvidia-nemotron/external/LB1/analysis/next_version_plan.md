# Next-version plan — `lb1-v1`

> Post-competition plan derived from the **1st Place Solution** (Public 0.91 / Private 0.920).
> **Status: PLAN ONLY.** No GPU training, no Kaggle submit, no kernel push, no dataset upload now
> (`allow_gpu_training/kaggle_submit/kaggle_kernel_push/dataset_upload = false`). The competition has ended;
> this is reusable methodology for the next symbolic-reasoning competition and for closing our own postmortem loop.
> Anchors: `gap_analysis.md`, `score_tricks.md`, `method_summary.md`, `../writeup/lb1-writeup.md`.

## Version name
`lb1-v1`

## Hypothesis
The ~+0.07 (private) gap from our 0.85 to LB1's 0.92 is **almost entirely** in cryptarithm and bit manipulation, and is **closable without RL** by re-expressing per-category solvers as **memorizable catalogs verified by short in-trace computation**, trained on **large rule-enforced programmatic synthetic data**, with traces **HEX-compressed** to fit the 7680-token budget. Specifically:
1. A **signature catalog + candidate-count memorization + DFS** trace will lift cryptarithm from our ~stuck state toward ~0.90+ on that category.
2. **HEX compression + extra bit rule families + rule-sequence catalog + Hamming repair** will lift bit manipulation toward ~0.92+ on that category.
3. **Re-testing the equation-numeric "global cipher" premise**: equation-numeric *deduce* (seen operator) is per-prompt 24-rule operators and ~95% solvable; our EQ "unrecoverable PRF" verdict likely applies only to the *guess* (unseen-operator) subset.

## What we borrow from LB1 / 1st Place
- Memorization-vs-computation split as the organizing principle (catalogs memorized, consistency computed).
- Cryptarithm: **signature normalization** (`L+R+output` → A,B,C,…), **4,205-signature catalog** with rule + slot-digit-strings + **candidate count**, **anchor = min candidate count**, `sig8` early-multiplication rule, **Observation 1 (mode)** and **Observation 2 (group)** pruning, **join/join_swap** first-pass.
- Bit: **HEX compression** of bit columns (length ≥4), **extra rule families** (maj, par3, ch, sel_nand_xnor, ao/oa/ax/ox/xa/xo), **rule-sequence catalog** (~5,238 valid 8-rule sequences) + **Hamming-distance repair** (≤32 nearest candidates, apply first matching all 8 bits).
- Equation: **24-rule inventory** + operator priors (`+/-/*`) for the deduce subset.
- Cipher: **plaintext vocabulary constraint** (the ~77-word train set).
- Trace as **explicit staged procedure** (Parse → Join-first → Rule table → Candidate rows → Search → Query), not free CoT.
- A **low-LR continuation phase** weighted to the weakest category.

## What new ideas we add (beyond LB1)
- **Re-cracking equation-numeric** under the per-prompt 24-rule hypothesis (our EQ-0/EQ-2′ assumed a single global function; LB1's 95% deduce contradicts this) — a cheap probe before any training.
- **Adapter souping on top of the catalog model**: LB1 used a single adapter; our validated +0.01 soup lever (insights.md) might stack on a stronger base. Test soup(catalog-model, replay-v14) — but expect catalogs to dominate.
- **Catalog-coverage local metric**: measure "% of train solvable *within 7680 tokens by the trace*" per category as the primary offline signal (LB1's table but without the leakage — generate the catalogs on a held-out split).
- **Faithfulness guard for the repair trick**: LB1's "fix only the final `\boxed{}`" trains non-faithful traces; we add a flag + an ablation so we can measure whether it helps or teaches hallucinated corrections.

## Data / corpus plan
- Base: our existing huikang recording-order corpus + replay-math (keep as the clean backbone; do NOT dilute it — protect against the regression we saw in b1/b2/v15/c1/c2).
- New synth, generated **programmatically** (no LLM authoring), skeleton-sampled from `train.csv` statistics, consistency-filtered, enforcing Obs.1/Obs.2:
  - cryptarithm: target order **80k–120k** traces (LB1 used 120k main). Q&A note: ~80k is where candidate-count recall stabilized → **floor 80k**.
  - bit: **40k–90k** traces, HEX-compressed.
  - equation-numeric (deduce): 10k–20k.
  - cipher/numeral/unit/gravity: ~10k each, mostly to preserve coverage.
- All trace token counts logged; target median bit trace < 5,000 tokens after HEX.
- **No weights/checkpoints/large datasets committed to git** (artifacts → object storage / `artifacts/`).

## Prompt format
- Reuse competition templates verbatim (already matched). Trace body = staged procedure with deterministic section headers; finality line `</think>\n\boxed{...}` at the tail (matches our insights.md:18 convention).

## Solver / synthetic generation plan
1. Build `signature_catalog.py`: enumerate 100×100 operands × 22 non-join rules → normalize → signatures → {rule, slot-digit-string, candidate count}. Verify count = 4,205 (sanity check vs LB1).
2. Build `rule_sequence_catalog.py`: enumerate valid 8-bit transforms from the rule list → normalize to 8-rule sequences → dedup. Verify count ≈ 5,238.
3. Extend `lib/nemo_solver.py` cryptarithm path to **emit the staged DFS trace** using catalog lookups; bit path to emit **HEX columns + repair** trace.
4. Synth generator: sample skeletons, assign rules under Obs.1/Obs.2, render prompts, run solvers to render traces, keep only internally consistent puzzles.

## Training config (when GPU is authorized — NOT now)
- Base Nemotron-3-Nano-30B, LoRA rank 32 / alpha 32; targets q/k/v/o + in/out + up/down/gate + lm_head (drop lm_head if it confirms no effect).
- Optimizer adamw_bnb_8bit, cosine; main LR 2e-4, ~1 epoch; **continuation LR 1e-5** weighted to the weakest category.
- Framework Unsloth (or our CCE replay recipe — compare). seq len ≥ 8192 (eval cap 7680).
- Effective batch size 16. **Scale to available GPU** — full 119h main is RTX-Pro-6000-only and out of scope for a live Kaggle-kernel competition; plan a **down-scaled** run (e.g. 20–40k cryptarithm + 20k bit, 1 epoch) for the post-comp RTX Pro 6000 to validate the *method*, not to match LB1's volume.

## Validation plan (incl. T12 hard-val)
- **T12 hard-val** (existing `lib/official_metric.py` + hardest-72) as the hard-tail hint (NOT primary — INS-002: it mispredicts atypical adapters).
- **Primary offline metric**: catalog-coverage-within-budget on a held-out 15% split, per category.
- Per-category accuracy on the 15% split with the official extractor.
- Watch the known regression: confirm augmentation does **not** drop hardest cipher/bit below base.

## Local official-like metric / extraction checks
- Port LB1's "correct within first 7680 tokens" rule into our scorer: if a trace exceeds 7680 but the answer extracted from the truncated trace is correct, count it correct.
- `\boxed{}` exact-match for strings, relative-error 1e-2 for numerics (matches grader).
- Trace token-length histogram per category (gate: bit median < 5,000).

## Submit / no-submit gate
- **Competition is over → no live submission. Gate is N/A now.**
- For a future live run, reuse our discipline: submit only if the candidate beats the held-best on the **aggregate LB** AND does not regress the hard slice on hard-val by >1 item; pick true best (avoid the auto "2 highest public" trap, submissions.md:47); respect the per-day quota.

## Expected upside
- Cryptarithm: from stuck toward ~0.90 category accuracy (LB1: deduce 38% model / but full path → 0.908 private overall after the catalog).
- Bit: from ~10% solver coverage toward ~0.92 category (LB1 bit model 93.45% within budget).
- Overall: a *method*-validated path from 0.85 → low-0.9s **if** GPU volume were available; realistically, post-comp we validate the **mechanism** (catalog lookup + HEX + repair appear in traces and lift the down-scaled model), not the full 0.92.

## Risks
- **Compute**: LB1's volume (>1B tokens, 170h single-GPU) is the real moat; a down-scaled run may under-deliver and confound "method works" with "not enough data."
- **Equation premise**: if our EQ-0/EQ-2′ global-cipher finding is actually correct for the deduce subset too, the equation re-test yields nothing (cheap to check first).
- **Repair faithfulness**: the "fix only `\boxed{}`" trick may teach hallucinated final-answer overrides — ablate.
- **Catalog reproduction**: LB1's code is unreleased; signature/rule-sequence catalogs must be re-derived from the prose (counts 4,205 / 5,238 are our sanity checks).
- **Dilution**: repeating the b1/b2/v15 mistake of diluting the clean recipe — protect the backbone.

## GPU time estimate (for a future authorized run)
- LB1 reference: ~2.3h / 20M tokens on RTX Pro 6000 Blackwell. Full LB1 ≈ 170h.
- Our **down-scaled validation** (≈60M–120M tokens, ~40k cryptarithm + 20k bit + small others, 1 epoch): ≈ **7–14h** on the RTX Pro 6000. Catalog generation (CPU): hours, no GPU.
- Inference/eval sweep on the 15% split: a few GPU-hours.

## Implementation checklist
- [ ] Cheap, no-GPU: re-test equation-numeric per-prompt 24-rule hypothesis on `train.csv` (probe; settle the premise conflict).
- [ ] Build & verify `signature_catalog.py` (expect 4,205 signatures).
- [ ] Build & verify `rule_sequence_catalog.py` (expect ~5,238 sequences).
- [ ] Extend `lib/nemo_solver.py`: staged cryptarithm DFS trace + HEX bit trace + repair.
- [ ] Implement HEX compression for traces (length ≥4 → hex); add token-length histogram.
- [ ] Synth generator with Obs.1/Obs.2 enforcement + consistency filter.
- [ ] Port "correct within 7680 tokens" into the local scorer.
- [ ] (GPU-gated) down-scaled SFT + continuation; record metrics under `runs/`.
- [ ] Hard-val + per-category 15%-split eval; check no hard-slice regression.
- [ ] (If live) submit/no-submit gate; else write up method-validation results.

## Rollback / hold-best strategy
- **Hold-best = our soup (Public 0.86 / Private 0.85)** and post-deadline **eq-aug (0.86/0.86)**. Any `lb1-v1` artifact must beat these on the offline metric before it is considered; if a trained `lb1-v1` regresses, **revert to the held-best** and keep `lb1-v1` only as a documented method experiment.
- All `lb1-v1` work lives on a branch / under `runs/`; no overwrite of the held-best adapters; no force-push.
