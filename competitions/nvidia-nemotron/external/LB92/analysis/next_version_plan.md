# Next-version plan — borrowing from LB92 (post-Saturday GPU reset)

> Updated 2026-06-17 from the actual writeup (`temp/LB92.pdf`). Analysis/planning only (no GPU/submit/push in
> this task). LB92's contribution is **data-engineering + training stability**, not a new paradigm. Borrows
> from an untrusted competitor writeup — verify before trusting. Complements `v16-evalfix` (LB25) and
> `v17-discovery`/`v17-dpo` (LB80).

## Version name
**v18-stable** — "per-char tokenization + grad-clip 1.5 + statistics-matched synthetic" (v14 backbone).

## Hypothesis
Two cheap, high-confidence levers reduce *lost* accuracy without touching the recipe: **(a) per-character
tokenization** stabilizes learning on the symbol categories (equation/cipher/cryptarithm) where BPE merges
hurt; **(b) gradient clipping at 1.5** removes the submission-to-submission variance our 1e9-off setting risks
(gradient explosions). A third, medium-confidence lever: **statistics-matched synthetic data with gap-closing
QC** can *add* signal where our naive synth (b1/b2/v15) diluted — if (and only if) it matches train.csv
statistics and is validated by the synthetic-vs-original eval gap.

## What we borrow from LB92
1. **Per-character tokenization** for equation/cipher/cryptarithm — synthetic tokens forcing 1 symbol = 1 token.
2. **Gradient clipping = 1.5** (replacing our 1e9-off) — to cut run-to-run variance.
3. **Statistics-matched synthetic generator + synthetic-vs-original gap QC**, final dose ~**2.5:1 synth:original**
   ONLY if the gap-validation passes (else keep low-dose; our naive synth regressed).
4. **Protect-the-easy-cats** discipline (don't regress 100%-categories).

## What we add / keep (ours, validated)
- v14 replay backbone + SVD model-soup (INS-004; LB92 doesn't soup — our edge).
- Keep eq-aug standalone; pair with LB80's **discovery-CoT** idea for equation (orthogonal to LB92's coverage lever).
- T12 hard-val gate; selection discipline (best + diverse hedge).

## Data / corpus plan
- **Tokenizer change first** (per-char for the symbol categories) — verify it doesn't break the easy cats.
- Statistics-matched synth: extract char-freq / numeric-range / transform-method distributions from train.csv;
  generate; **train-synth / eval-both / close-the-gap** until synthetic eval ≈ original eval; then mix at the
  validated ratio (start ≤15%, only go toward 2.5:1 if the gap QC + T12 both hold).
- Own-work generation only (no high-dose external teacher — regressed at 0.81).

## Prompt format / training config
- Eval-faithful prompt; response-only mask; seq 8192; all-linear LoRA r32 (excl. gate_proj — LB80).
- **`max_grad_norm = 1.5`** (the LB92 change; A/B vs our 1e9-off to confirm it reduces variance, not just changes it).
- LR 3.5e-4, 2 epochs, AdamW β2 0.95, linear decay, warmup 0; 7h guard + fail-fast preflight.

## Validation plan (incl. T12 hard-val) — gate BEFORE any submit
1. **Tokenizer sanity**: per-char tokenization doesn't regress cipher/gravity/numeral/unit (the 100% cats).
2. **Synthetic-vs-original gap QC**: synthetic eval ≈ original eval before trusting the generator.
3. `validate_kernel.py` + fail-fast preflight.
4. **T12 local official metric** on `eval/hard_val_ids.json`; require **no easy-cat regression**, total ≥ 0.764.
5. **Variance check**: train the same config ≥2× and confirm grad-clip 1.5 narrows the score spread vs 1e9.

## Submit / no-submit gate
- Submit only if T12 ≥ 0.764, no easy-cat regression, and the variance check favors clip-1.5.
- **Late-window submission needs explicit human approval** (analysis-only task). Soup-grow only if local metric improves.

## Risks
- **Per-char tokenization can hurt the easy/numeric cats** (changes token boundaries everywhere) — gate on easy-cat parity.
- **Grad-clip 1.5 tension** with LB80/our "off" — treat as an A/B, not gospel.
- **Statistics-matched synth can still dilute** if the gap QC is imperfect — keep dose conservative; T12-gate.
- LB92 reached only ~0.86 with all this — modest expectations; these reduce *lost* accuracy, not break the ceiling.

## GPU estimate
- Tokenizer + generator + gap-QC work: **CPU, ~0 GPU**. Training + variance A/B: **1–2 RTX PRO 6000 sessions** (~6–7 h each).

## Implementation checklist
- [ ] (CPU) per-char tokenization for symbol categories (synthetic tokens); verify reversible + easy-cat-safe
- [ ] set `max_grad_norm = 1.5`; A/B vs 1e9-off (≥2 runs each) → variance check
- [ ] (CPU) statistics-matched generator (char-freq / numeric-range / transform-method dist); synthetic-vs-original gap QC
- [ ] train v18-stable: per-char tok + clip 1.5 + gap-validated synth (≤15% → up to 2.5:1 if QC holds)
- [ ] T12 hard-val (no easy-cat regression, ≥0.764) + variance check
- [ ] gate passes → human approval → submit; soup-grow + diverse hedge
