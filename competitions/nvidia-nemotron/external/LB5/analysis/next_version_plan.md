# Next-version plan — `lb5-v1`

> Post-competition plan derived from the **5th Place Solution** (Private 0.900).
> **Status: PLAN ONLY.** No GPU training, no Kaggle submit, no kernel push, no dataset upload now
> (`allow_* = false`; competition ended). Reusable methodology. Anchors: `gap_analysis.md`, `score_tricks.md`, `method_summary.md`, `../writeup/lb5-writeup.md`.

## Version name
`lb5-v1`

## Hypothesis
Our 0.85→LB5 0.900 gap (~+0.05 private) is closable **without RL and without solving cryptarithm**, primarily via (1) **iterative LoRA averaging / multi-seed model soup as a training-time regularizer** (turns an unstable ~0.87 into a stable ~0.90), (2) an **infinite no-leakage synthetic generator** that makes our CV track the **private** LB, (3) a **ternary-extended byte-level bit solver** (→ ~94%), and (4) a **2-world/4-family/13-rule equation solver** (→ ~96%, also the 3rd refutation of our equation-cipher premise). Cryptarithm is explicitly **deprioritized** here (LB5 hit 0.90 with 7.9% cryptarithm); it remains the 0.90→0.92 lever covered by `lb1-v1`/`lb3-v1`.

## What we borrow from LB5 / 5th Place
- **Iterative LoRA averaging**: average the model before/after each training step (phase-2 style); and **multi-seed soup** — train N models from one checkpoint with different problem sets/seeds, then average (phase-3 style) to cancel errors.
- **No-leakage generator**: synthesize ALL training data (statistics-matched to train.csv: ranges, vocab, 4 cipher formats, noise); validate **only** on train.csv → private-tracking CV.
- **Bit**: ternary byte-level (MAJORITY/CHOICE/XOR-NOT_OR), 15 primitives, memorized continuations/sequences (prune to train-necessary), **raw bits** (NOT merged-token encodings), **cut to ~7 examples**, group-by-shift-length filters, ternary by prefix/suffix extrapolation.
- **Equation**: 2-world/4-family/13-rule solver, deterministic priority, family-based guessing.
- **Training**: multi-round high-LR SFT (sample all categories → no forgetting); LR 1e-4→2e-4, grad_clip 1.0, linear; @huikang trainer; **no quant/packing**; **no DoRA**.
- **CoT**: full logical CoT (short/guess CoT fails); trust validation/LB over loss.

## What new ideas we add (beyond LB5)
- **Combine LB5 soup-stability with LB1/LB3 cryptarithm**: use iterative LoRA averaging to stabilize a model that *also* carries LB3's two-stage cryptarithm — get LB5's stability AND the cryptarithm lever (target >0.90).
- **HEX vs raw-bits A/B**: LB1/LB3 succeeded with HEX; LB5's encoding broke the model. Test our tokenizer to find a compression that doesn't merge into single tokens (e.g. spaced hex) — resolve the cross-writeup tension.
- **Equation-deduce re-crack (no GPU)**: implement the 13-rule per-prompt solver on `train.csv`; settle our global-cipher verdict (shared with `lb1-v1`/`lb3-v1`).
- **Hybrid CV**: LB3's leakage-controlled hold-out + LB5's no-leakage generator validation — cross-check both track private.

## Data / corpus plan
- Build an **infinite generator** per category (statistics-matched, noised, unique-answer-guaranteed). Validate only on train.csv (no training on it).
- Bit-heavy mix early (like LB5), equation ramp later. Protect easy 100% categories.
- No weights/checkpoints/large data in git (artifacts → object storage / `artifacts/`).

## Prompt format
- Competition templates verbatim; **full logical CoT** with explicit deduction steps; finality `</think>\boxed{...}`. Avoid token-saving encodings that merge into single tokens.

## Solver / synthetic generation plan
1. `gen_*.py` per category (gravity/conversion/cipher/roman/bit/equation/cryptarithm) — statistics-matched, noised.
2. `bit_ternary_solver.py`: 15 primitives, 42 unaries, 4 stages, memorized continuations (prune to train-necessary), raw-bit CoT, 7-example cut, group/extrapolate filters.
3. `equation_solver.py`: 2-world/4-family/13-rule, deterministic priority, family guessing.
4. Reuse @huikang cryptarithm CoT (deprioritized) or graft LB3's two-stage if aiming >0.90.

## Training config (when GPU authorized — NOT now)
- Base Nemotron-3-Nano-30B; LoRA rank32/α32; LR 1e-4→2e-4; grad_clip 1.0; linear; @huikang trainer (no quant/packing).
- **Phase 1**: multi-round high-LR SFT (all categories each round).
- **Phase 2**: LoRA averaging regularization (average before/after each step).
- **Phase 3**: multi-seed soup (train 3 from one checkpoint, average).
- **Down-scale for post-comp RTX Pro 6000**: LB5 used ~2B tokens over 15 iterations. A down-scaled run (a few iterations, ~100–300M tokens) ≈ **10–25h** — validate the *mechanism* (soup stability, no-leakage CV tracking private, bit ternary lift), not LB5's full volume.

## Validation plan (incl. T12 hard-val)
- **Primary**: no-leakage generator-vs-train.csv validation; verify it correlates with our known LB points (private-tracking).
- **Secondary**: T12 hard-val as a hard-tail hint (INS-002 caveat).
- Per-category oracle solvability + per-iteration tracking; verify soup phases are <1% unstable (LB5's stability claim).

## Local official-like metric / extraction checks
- `\boxed{}` exact (strings) / rel-1e-2 (numerics); "correct within 7680 tokens"; per-category accuracy; token-length histograms (target: bit fits via 7-example cut).

## Submit / no-submit gate
- **Competition over → no live submission; gate N/A now.** Future live: select on the **private-tracking CV** (not public, which plateaus); soup-stabilized adapters reduce selection variance. Respect quota.

## Expected upside
- Stability: convert an unstable ~0.87 into a stable ~0.90 (LB5's core result). Bit → ~94%; equation → ~96%. Realistically post-comp we validate the **mechanism** (iterative soup stability, no-leakage CV tracking private, ternary bit lift), not the full 0.90.

## Risks
- **Compute**: ~2B-token, 15-iteration pipeline is heavy; a down-scaled run may under-deliver.
- **Equation premise**: if our global-cipher verdict holds for deduce too (unlikely given 3 refutations), the re-test yields nothing (cheap to check).
- **Encoding tension**: HEX may break our model like LB5's encoding — must validate tokenization first.
- **Attribution opacity**: LB5 itself can't isolate whether gains came from CoT vs trainer vs soup — our ablations must be cleaner (single-change isolation, per LB3).
- **Generator fidelity**: a generator diverging from the official one can create/remove hidden artifacts (LB5's own warning) — match statistics carefully.

## GPU time estimate (for a future authorized run)
- LB5 reference: ~2B tokens, 15 iterations, 100% Kaggle (≤12h/notebook) + ~$100 Colab Pro.
- Our down-scaled validation: ≈ **10–25h** on the RTX Pro 6000. Generation: CPU, hours.

## Implementation checklist
- [ ] No-GPU: equation-deduce re-crack with the 13-rule per-prompt solver on `train.csv` (settle the premise; shared with `lb1-v1`/`lb3-v1`).
- [ ] HEX-vs-raw-bits tokenizer probe (no merged tokens).
- [ ] Build the no-leakage per-category generator (statistics-matched, noised).
- [ ] Build `bit_ternary_solver.py` (15 primitives, continuations, raw-bit CoT, 7-example cut).
- [ ] Build `equation_solver.py` (2-world/4-family/13-rule + family guessing).
- [ ] Implement iterative LoRA averaging (phase-2) + multi-seed soup (phase-3) in our trainer.
- [ ] Build the private-tracking generator-vs-train.csv validation.
- [ ] (GPU-gated) down-scaled 3-phase run; record under `runs/`; verify <1% soup stability.
- [ ] Eval: per-category + stability; confirm CV tracks our known LB points.
- [ ] (If live) select on the private-tracking CV; else write up method-validation results.

## Rollback / hold-best strategy
- **Hold-best = our soup (Public 0.86 / Private 0.85)** + post-deadline **eq-aug (0.86/0.86)**. Any `lb5-v1` artifact must beat these on the offline metric before consideration; on regression, **revert to held-best** and keep `lb5-v1` as a documented method experiment. All work on a branch / under `runs/`; no held-best overwrite; no force-push.
