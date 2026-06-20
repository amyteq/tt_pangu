# LB5 / 5th Place — Score-improvement tricks

> Evidence cites `../writeup/lb5-writeup.md` (= `temp/LB5.pdf`) unless noted. "reusable by us" judged vs our repo (notes.md / submissions.md / insights.md).
> Author explicitly notes improvement attribution is **unclear** (many simultaneous changes); impacts below are qualitative.

| trick | description | evidence | likely impact | reusable by us? | difficulty |
|---|---|---|---|---|---|
| **Iterative LoRA averaging / model soup (as regularizer)** | Phase 2: average model before/after each training step. Phase 3: train 3 models from one checkpoint with different problem sets, then average (cancel errors / avoid bad minima). Across 15 iterations. | §III Training Loop | **High** (stability; the title technique) | **Yes — extends our soup lever.** We soup once post-hoc; LB5 soups iteratively *during* training. | Medium |
| **Infinite no-leakage synthetic generator + honest CV** | Generate all training data; use `train.csv` only for validation → CV correlates with **private** LB. | §II, §Validation | **High** (decision signal) | **Yes — strong validation upgrade** (complements LB3's leakage-controlled hold-out) | Medium-High |
| **Ternary-extended byte-level bit solver** | Add MAJORITY/CHOICE/XOR-NOT_OR to @huikang's byte-level; 15 primitives; **memorize continuations/sequences** (pruned ~140/7500 → ~30/1500); raw bits; group-by-shift-length filters; ternary by prefix/suffix extrapolation (no search). | §II.5; bit 94.3% | **High** (bit category) | **Yes** — our bit solver is ~10% coverage | High |
| **2-world / 4-family / 13-rule equation solver** | NORMAL/REVERSE (String/Integer reversal); 4 families, 13 rules; ≤1 rule/family; deterministic priority `REVERSE>NORMAL`, `Integer>String`, `subab>posabs>negabs>subba>mod`. | §II.6; deduce ~95% | **Medium-High** | **Yes — re-check our EQ premise** (3rd refutation) | Medium |
| **Operation-family guessing (equation)** | Each family appears once → for unseen query, pick from an unused family (`no SUB→subab`, `no ADD→add`, `no MUL→mul`). | §II.6; guess ~40% | **Medium** (guess subset) | **Yes** | Low |
| **Phase-3 lookup-string disambiguation (equation)** | Encode appearing operator rules (in order) into a lookup string to pick the true query rule → ~96%. | §II.6 | **Low-Medium** (helped public, not chosen private) | **Maybe** | Medium |
| **Multi-round high-LR SFT (no forgetting)** | 6 iterations, LR 1e-4→2e-4, sample all categories each round → no catastrophic forgetting; copies CoT format perfectly. | §III phase 1 | **Medium** | **Yes** | Low |
| **Cut to ~7 examples** | Use only ~7 of 7–10 examples (≈94% accuracy) to save the 7680-token budget; no padding to 10. | §II.5 fixes | **Medium** (token budget) | **Yes — cheap** | Low |
| **Roman lookup-table CoT** | Custom CoT writes a 1–100 table, verifies examples, pulls the answer. | §II.4 | **Low** (already 100%) | **Yes** | Low |
| **`A B` spacing / avoid single-token encodings** | Token-saving 2-letter encodings **broke the model** (single-token `AB`); raw bits worked. | §II.5 (failure) | **High (negative lesson)** | **Yes — caution for our HEX** | Low |
| **No quantization / no packing (Mamba SSM)** | Unsloth + 4-bit + packing broke Nemotron; @huikang's trainer (no quant/packing) worked. | §V.4 | **High (negative lesson)** | **Yes — avoid** | Low |
| **GRPO / pseudo-GRPO-via-DPO** | Tried; failed (Kaggle air-gapped; 5 DPO iterations couldn't learn easy bit). | §V.2 | **Negative** (don't) | **Avoid** on Kaggle | High |
| **DoRA** | Lower loss but vLLM unsupported; DoRA→LoRA conversion lossy → kept LoRA. | §V.5 | **Negative** | **Avoid** for this grader | Low |

## Provenance / attribution
- **Built on @huikang** (CoT generator, training notebook, byte-level bit approach, cipher/gravity/conversion CoT, fallback cryptarithm CoT). **@donaldgalliano** (per-bit insight — *rejected* as not generator-intended). **@citerne** (Kaggle CLI tutorial). arXiv: GRPO=DPO (2510.00977), ORPO (2403.07691), KTO (2402.01306), DPOP/Smaug (2402.13228), DoRA (2402.09353).
- **Novel to LB5 (vs prior art and vs LB1/LB3):** the **infinite no-leakage generator → honest CV** discipline, the **iterative LoRA averaging as a training-time regularizer**, and the **ternary byte-level bit solver with memorized continuations + group/extrapolate filters**. (LB5 explicitly **fails** on cryptarithm, the lever LB1/LB3 use.)
- **Cross-writeup tension worth noting:** LB1/LB3 succeed with **HEX/encoding** compression; LB5's **encoding broke the model** (revert to raw bits). Likely a tokenization-granularity difference — caution for any HEX work we do.
