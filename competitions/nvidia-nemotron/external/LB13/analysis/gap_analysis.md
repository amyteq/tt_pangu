# LB13 / 13th Place — Gap analysis (us vs the 13th-place writeup)

> "our approach" cites `competitions/nvidia-nemotron/{notes,submissions,tracking,insights,equation-frontier,bugs}.md`.
> "writeup" cites `../writeup/lb13-writeup.md` (= `temp/LB13.pdf`). `unknown` where the repo records nothing.
> Our best: **soup (v14+c1+b1) Public 0.86 / Private 0.85**. LB13: 13th (teacher oracle 89.4%; no final LB number).

| area | our approach | writeup approach | evidence | gap | lesson |
|---|---|---|---|---|---|
| **corpus construction** | huikang corpus + replay-math + small synth. (submissions.md:101) | @huikang reasoners + task heuristics to raise teacher correctness; **rebalance 1:1 correct:incorrect**; 3× cryptarithm seeded from equation. (writeup §2) | submissions.md:101; writeup | Theirs optimizes teacher solved-fraction + keeps failures | Improve teacher correctness; keep & balance incorrect traces |
| **reasoning traces** | Verified solver-CoT; bit 10%, equation 0.4%. (notes.md:72-73) | Oracle: bit 89.7%, equation_deduce 95.3%, equation_guess 50.7%, cipher/trivials 100%, cryptarithm ~10%. (writeup table) | notes.md:72-73; writeup | Our coverage far lower | Sharpen per-category reasoners |
| **synthetic data** | b1/b2/v15 diluted; c1/c2 keep **only solver-correct**. (submissions.md:31) | **Keep teacher-incorrect traces, rebalanced 1:1**; robust aggregation (match ≥1 example). (writeup §2) | submissions.md:31; writeup | We discard failures; they keep+balance | **A/B keeping failed traces** (echoes LB10) |
| **cryptarithm** | Synth-only; 8%→71% local, total ~0.86 (B8). (bugs.md:14) | **~10% oracle**; de-brace output + non-operator-symbol fallback + 3× augmentation. (writeup §2) | bugs.md:14; writeup | Both weak | cryptarithm still the unsolved lever (LB1/LB3 needed) |
| **bit manipulation** | ~90% unsolved. (notes.md:73) | **3-input verification (MAJ/XNOR)** + bit-position-restricted search + left-edge fallback → 89.7%. (writeup §1) | notes.md:73; writeup | We lack 3-input verification | 3-input op verification is key to bit coverage |
| **hard categories (bit/equation/symbol)** | equation = global cipher (EQ-0/EQ-2′). (equation-frontier.md:209-228) | **equation_deduce 95.3% / guess 50.7%** via category-exclusivity + **reversal symmetry shared across examples** + majority-vote reversal. (writeup §3) | equation-frontier.md:266-269; writeup | **Premise conflict — 6th independent confirmation; highest guess (50.7%)** | equation is per-prompt operators; the symmetry+exclusivity model even cracks half the guess set |
| **validation & hard-val** | T12 late, atypical-adapter-fragile. (submissions.md:76-78) | Reports teacher oracle per category as the optimization target. (writeup table) | submissions.md:76-78; writeup | Theirs targets teacher solved-fraction | Track per-category teacher oracle as the ceiling |
| **local metric alignment** | Official metric ported late. (notes.md:218-220) | Oracle solved-fraction per category. (writeup) | notes.md:218-220; writeup | Theirs is oracle-relative | Measure teacher oracle first |
| **prompt format** | CoT ends `</think>\boxed{}`. (insights.md:18) | De-brace cryptarithm output; drop bit parsing-display to free tokens. (writeup §1-2) | insights.md:18; writeup | Format hygiene to reduce ambiguity/tokens | Trim trace syntax that confuses matching/budget |
| **sequence length / truncation** | seq 8192; truncation bugs (B4). (notes.md:271-274) | Free token budget by dropping parsing-display; upsample hard cats in stage 3. (writeup §1, SFT) | notes.md:271-274; writeup | They budget for verification | Free budget for the verification steps |
| **LoRA / adapter config** | rank-32, MoE-128 tying, lm_head. (notes.md:117-118) | rank/alpha 32/32, dropout 0, q/k/v/o + in/out + up/down (**no lm_head**); **3-stage decreasing LR** (2e-4→2e-5→5e-6). (writeup §SFT) | notes.md:117; writeup | Multi-stage decreasing LR; no lm_head | A/B 3-stage decreasing-LR; drop lm_head (vLLM ignores it) |
| **adapter merge / ensemble** | One-shot SVD soup → 0.86. (insights.md:44-54) | No merge; single 3-stage adapter. (writeup §SFT) | submissions.md:91; writeup | They didn't merge | Multi-stage SFT is an alternative to souping |
| **packaging / submission** | Manual final pick. (submissions.md:47) | `unknown` (not detailed). | submissions.md:47; writeup | — | — |
| **experiment tracking** | Rich docs. (tracking.md) | Per-category oracle deltas (87.7%→89.4%). (writeup) | tracking.md; writeup | Comparable | Track per-category teacher deltas |

## Why our EQ1..EQ4 / T12 / replay / synthetic / merge attempts did not close the gap
- **EQ1..EQ4:** equation_deduce 95.3% / **guess 50.7%** (LB13) — **6th independent refutation** (LB1 95%, LB3 93%, LB5 96%, LB6 ~93%, LB10 93.1%). LB13's **reversal-symmetry + family-exclusivity** model is the most actionable structure to adopt; it even cracks **half** the guess set. Our global-cipher verdict is decisively wrong for deduce. Re-test (no GPU).
- **T12 hard-val:** We never tracked **per-category teacher oracle** as the optimization target.
- **replay (v14):** Generic lever; doesn't sharpen reasoners.
- **synthetic (c1/c2):** We keep **only solver-correct** rows; **LB13 keeps teacher-incorrect traces and balances them 1:1** (LB10 confirms excluding them hurts). A/B this on our data.
- **merge/soup (0.86):** LB13 didn't merge — a **3-stage decreasing-LR SFT** reached its result; merge isn't the only path.

## High-value vs not-worth-it (for future competitions)
**High value (do):** the **equation reversal-symmetry + family-exclusivity model with majority-vote reversal** (highest guess 50.7%); **keep & rebalance teacher-incorrect traces 1:1** (A/B vs our verified-only); **robust aggregation** (match ≥1 example); **bit 3-input verification** (MAJ/XNOR); **3-stage decreasing-LR SFT** (align → smooth → upsample-hard); re-test the equation premise.
**Too expensive / not worth (skip):** chasing cryptarithm with fallback-only heuristics (10% — needs LB1/LB3 structure); lm_head in LoRA targets (vLLM ignores it).
