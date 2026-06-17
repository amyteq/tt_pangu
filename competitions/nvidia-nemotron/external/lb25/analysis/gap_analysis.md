# LB25 gap analysis — huikang's ~0.872 vs our 0.86

> What LB25 (Tong Hui Kang's Progress-Prize + improvements, ~0.872 public) did that our best own-work
> (0.86 soup / 0.85 private; eq-aug 0.86 private post-deadline) did not — and what is worth borrowing.
> External claims are untrusted (see `../source_index.md`); our numbers are from `tracking.md`/`submissions.md`.

## Side-by-side

| dimension | LB25 (huikang) | us | gap / verdict |
|---|---|---|---|
| base / adapter | Nemotron-3-Nano-30B, LoRA r32 (MLP+attn+lm_head) | same, r32 (MoE-tied + lm_head + Mamba in/out_proj) | parity |
| paradigm | **pure SFT**, deterministic-solver CoT | pure SFT (replay recipe) + SVD model-soup | parity on SFT; **soup is ours, not theirs** |
| reasoning traces | **deterministic algorithm traces** (solver emits the steps; model executes verbatim) | replay corpus (huikang corpus) + some verified-solver-CoT (c1/c2) + synth (b1/b2/v15) | **GAP: we never made the solver *itself* the CoT author across all categories** |
| underfit handling | **min-logprob selective replay** (replay only still-underfit/hard sequences) | fixed replay-math dose; no adaptive per-row replay | **GAP: adaptive replay is untried and cheap** |
| batching | **category-stratified** mini-batches | not explicitly stratified | minor gap |
| output format | **short responses** (LB25 fix) to dodge `max_new_tokens`→blank-`\boxed{}` | long CoT at seq8192; we hit 0.85/0.86 so likely OK, but unverified | **GAP to verify: is any of our score lost to truncated CoT?** |
| warmstart | fine-tune **from the v27 adapter**, not base | each run from base | technique difference (cheap) |
| equation/cryptarithm | `cryptarithm_deduce` ~8.95% train **even with backtracking solver** | `equation` strong-cipher, eq-aug 0.86 via coverage-memorisation | **agreement: a hard wall; do not over-invest** |
| score | ~0.872 public | 0.86 public / 0.85 priv (eq-aug 0.86 priv) | **−0.012 gap, and it is NOT equation-driven** |

## Where the ~0.012 likely comes from (and where it does NOT)
- **NOT equation.** Both sides confirm the cryptarithm/equation cipher ceilings at ~8–9% and contributes
  little. Our eq-aug coverage lever and their backtracking solver hit the same wall. Equation is *bounded*.
- **Most likely: bit_manipulation + format reliability.** huikang's bit is 86.3% on *train* with a
  brute-force-solver CoT; the LB25 jump is credited to the **short-response format fix** (good reasoning that
  actually reaches a parseable answer) + min-logprob replay of the hardest bit rows. Our bit hard-val is
  strong (v14 14/16, soup 13/16), so our marginal headroom is the **format/length reliability** and the
  **adaptive replay of the residual hard bit/cipher rows**, not equation.

## Borrowable (ranked by EV, all SFT — no GPU-quota gamble beyond one run)
1. **Min-logprob selective replay** (HIGH EV, cheap). Score each training trace's min per-token log-prob after
   epoch 1; replay only the rows that stayed far from 0 (hardest bit/cipher). Adds signal exactly where SFT
   plateaus, without the dilution that uniform high-dose caused us (b2/v15/c2 regressions).
2. **Verify + fix output-length/format** (HIGH EV, ~free). Audit our submission's CoT length vs the 7,680
   `max_new_tokens` cap on the hardest rows; if any answers are getting truncated before `\boxed{}`, adopt a
   short-/bounded-response alignment pass (huikang's LB25 lever). This is "free accuracy" the metric rewards.
3. **Deterministic-solver CoT for bit** (MEDIUM EV). Expand our solver to emit huikang-style column-match
   diagnostic traces for bit; train the model to execute them. (Our `lib/nemo_solver.py` covered cipher/bit
   only partially; bit is the category with the most train-set headroom at 86.3%.)
4. **Category-stratified batching** (LOW-MEDIUM EV, ~free): even category coverage per step.
5. **Warmstart from our 0.86 soup** for any alignment fine-tune (cheap; preserves the banked recipe).

## NOT worth borrowing / already have
- Their single-adapter approach — **we already beat it with the model soup** (INS-004). Keep souping.
- Heavy investment in cryptarithm/equation — **confirmed ~8–9% wall both ways**; eq-aug 0.86 is our ceiling there.

## Open unknowns (see source_index)
- Whether the 0.872 recipe is tonghuikang's or `kuangyicheng`'s short-response variant (same thread).
- Exact min-logprob replay schedule and the short-response template — `unknown` (writeup body JS-blocked).
