# LB6 / 6th Place — Gap analysis (us vs the 6th-place writeup)

> "our approach" cites `competitions/nvidia-nemotron/{notes,submissions,tracking,insights,equation-frontier,bugs}.md`.
> "writeup" cites `../writeup/lb6-writeup.md` (= `temp/LB6.pdf`). `unknown` where the repo records nothing.
> Our best: **soup (v14+c1+b1) Public 0.86 / Private 0.85**. LB6: **2nd public / 6th private** (~0.90 private class).

| area | our approach | writeup approach | evidence | gap | lesson |
|---|---|---|---|---|---|
| **corpus construction** | huikang corpus + replay-math + small synth. (submissions.md:101) | Massive distribution-matched synthetic; two final sets ~0.25B / ~0.5B tokens; bit = 69%/66% of tokens. (writeup §3) | submissions.md:101; writeup | Ours small/bolt-on; theirs is the whole training set, bit-dominant | Scale synthetic to the distribution; bit needs the lion's share |
| **reasoning traces** | Verified solver-CoT; bit 10%, equation 0.4% coverage. (notes.md:72-73) | Template bit solver (1508/1602) + DFS cryptarithm/equation solvers with CoT. (writeup §2) | notes.md:72-73; writeup | Our hard-cat solvers far weaker | Build template + DFS solvers; emit them as CoT |
| **synthetic data** | b1/b2/v15 diluted, regressed hard slice. (submissions.md:31) | Distribution-matched; **targeted subsets** fix specific hallucinations; cryptarithm rerolls until solvable under budget. (writeup §3) | submissions.md:31; writeup | Ours diluting; theirs targeted + budget-aware | Match distribution; add targeted failure-case subsets |
| **cryptarithm** | Synth-only; 8%→71% local but total ~0.86 (B8). (bugs.md:14) | **DFS + reversed search** (~40% reversed) + op-deduction pruning; 240/654 deduce (lighter 170 shipped). (writeup §2) | bugs.md:14; writeup | We lack a real DFS solver | A plain DFS + reversed search + pruning is a viable cryptarithm path |
| **bit manipulation** | ~90% unsolved; no HEX. (notes.md:73) | Template set (incl. ternary MAJ/CH) + monotonic skips + **hex arithmetic + cheatsheet**; 1508/1602. (writeup §2) | notes.md:73; writeup | We never templated/hexed bit | Templates + hex + skips close the bit gap |
| **hard categories (bit/equation/symbol)** | equation = unrecoverable global cipher (EQ-0/EQ-2′). (equation-frontier.md:209-228) | **equation_numeric_guess 550/594 ≈ 93%** (deduce higher) via add/sub/mul families + maxmodmin. (writeup §2) | equation-frontier.md:266-269; writeup | **Premise conflict — 4th independent confirmation** | equation is per-prompt operators; our global-cipher verdict is wrong for deduce (and even guess ~93%) |
| **validation & hard-val** | T12 late, atypical-adapter-fragile; trusts public LB aggregate. (submissions.md:76-78) | **Full-train-as-validation** + **per-domain LB probing (DUMMY masking)**; inferred 250/250 test → 0.01≈3 problems. (writeup §1) | submissions.md:76-78; writeup | We lack per-domain attribution | DUMMY masking gives a pure per-domain signal — fixes our B8 |
| **local metric alignment** | Official metric ported late. (notes.md:218-220) | Full-train CV + per-domain LB probe; `-0/-1/-2` problem-count notation. (writeup §1) | notes.md:218-220; writeup | Theirs is per-domain and quantized to problems | Track per-domain solved-problem counts, not just aggregate |
| **prompt format** | CoT ends `</think>\boxed{}`. (insights.md:18) | Algorithmic CoT; DUMMY (`I will ignore...\n\boxed{DUMMY}`) for masked domains. (writeup §1-2) | insights.md:18; writeup | DUMMY-output trick is novel to us | Use a deliberate ignore-output to mask domains for probing |
| **sequence length / truncation** | seq 8192; truncation bugs (B4). (notes.md:271-274) | 7680 budget binding → hex to save tokens; cryptarithm rerolls until solvable *under limit*. (writeup §2-3) | notes.md:271-274; writeup | They design to the budget | Budget-fit synthetic by construction |
| **LoRA / adapter config** | rank-32, MoE-128 tying. (notes.md:117-118) | rank32/α32, BS 32, LR 3.5e-4, 1 epoch, Unsloth; Tinker late. (writeup §Overall) | notes.md:117; writeup | Similar; higher LR (3.5e-4) | A/B higher LR + Tinker for velocity |
| **adapter merge / ensemble** | One-shot SVD soup → 0.86. (insights.md:44-54) | Shipped **two seeds** of the 0.25B adapter (the selection that cost 2nd-3rd). (writeup §3) | submissions.md:91; writeup | Both use multi-seed/soup ideas | Two-seed shipping is a stability hedge; CV must be calibrated |
| **packaging / submission** | Manual final pick. (submissions.md:47) | Chose two seeds of the safer 0.25B over the riskier 0.5B (bit-CV estimate was off). (writeup §3) | submissions.md:47; writeup | Selection regret on a mis-estimated trade-off | Calibrate the bit/cryptarithm data trade-off before committing |
| **experiment tracking** | Rich docs; per-kernel sniff. (tracking.md) | Per-domain LB-probe results + solved-problem counts per template. (writeup §1-2) | tracking.md; writeup | Theirs is per-domain quantified | Track per-domain solved counts |

## Why our EQ1..EQ4 / T12 / replay / synthetic / merge attempts did not close the gap
- **EQ1..EQ4:** We called equation a **global cipher**; LB6's family-based DFS solves **equation_numeric_guess ~93%** — the **4th independent refutation** (LB1 95%, LB3 93%, LB5 96%). Re-test (no GPU).
- **T12 hard-val:** Late and not per-domain. LB6's **per-domain LB probing (DUMMY masking)** is exactly the attribution tool we lacked when stuck on B8 ("single-category gain ≠ total gain").
- **replay (v14):** Generic ceiling lever; doesn't build the solvers.
- **synthetic (b1/b2/v15/c1/c2):** Too small + diluting. LB6 shows **bit CV is fragile to any mix change** — our augmentation likely regressed bit exactly this way; the fix is to **over-weight bit** and match the distribution.
- **merge/soup (0.86):** LB6's two-seed shipping is a stability hedge, not a capability lever; the capability came from the solvers + validation.

## High-value vs not-worth-it (for future competitions)
**High value (do):** **per-domain LB probing (DUMMY masking)** — the attribution tool we lack; **full-train-as-validation** with distribution-matched synthetic; **template bit solver + hex + monotonic skips**; **DFS cryptarithm with reversed search + pruning**; **over-weight bit data** when scaling (it's fragile); **targeted hallucination subsets**; re-test the equation premise.
**Too expensive / not worth (skip / caution):** the **bit/cryptarithm data trade-off** without a calibrated CV (cost LB6 2nd-3rd); **hex** only after a tokenizer check (LB5's encoding broke the model); NOT-CH bit formula (too much training for the gain — LB6 dropped it).
