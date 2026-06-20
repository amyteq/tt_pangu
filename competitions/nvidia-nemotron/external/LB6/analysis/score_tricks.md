# LB6 / 6th Place — Score-improvement tricks

> Evidence cites `../writeup/lb6-writeup.md` (= `temp/LB6.pdf`). "reusable by us" judged vs our repo (notes.md / submissions.md / bugs.md).

| trick | description | evidence | likely impact | reusable by us? | difficulty |
|---|---|---|---|---|---|
| **Per-domain LB probing (DUMMY masking)** | Target domain → real CoT; all other domains → `I will ignore this problem\n\boxed{DUMMY}` → pure per-domain public-LB signal. | §1 Validation | **High** (attribution) | **Yes — top pick.** Directly fixes our B8 "single-cat gain ≠ total". Works on LB or a local set. | Low-Medium |
| **Full-train-as-validation** | Use all of train.csv (≈10× the 950 holdout) as validation; requires distribution-matched synthetic so train isn't trained on. | §1 | **High** (reliable CV) | **Yes** (3rd validation paradigm vs LB3 holdout / LB5 generator) | Medium |
| **Template bit solver + monotonic skips** | shl/shr/rotr + pairwise XOR/AND/OR/NOT + ternary MAJ/CH/NOT-CH; iterate shift values; skip monotonic branches when partial < result. | §2 bit; 1508/1602 | **High** (bit category) | **Yes** — our bit ~10% coverage | Medium |
| **Hex arithmetic + hex cheatsheet** | LLM computes exclusively in hex (incl. `<=` in hex); print a hex multiplication cheatsheet first. | §2 bit optimizations | **Medium** (token budget) | **Yes — but heed LB5's "encoding broke the model"**; validate tokenizer | Low-Medium |
| **DFS cryptarithm solver + reversed search** | Tree search over mapped equations (add/sub/mul families + maxmodmin); if forward fails, restart reversed (~40% solved reversed). | §2 cryptarithm; 240/654 deduce | **Medium-High** | **Yes** — plainer than LB1 catalog / LB3 CSP | High |
| **Operation deduction / leading-zero / leading-one / equation sorting** | Restrict each operator to 2-3 ops (length/sign/one-per-family); drop 0 from first digits; auto first-digit=1 for 3-digit add; search fewest-unknown equations first. | §2 cryptarithm optimizations | **Medium** | **Yes** — cheap pruning | Low-Medium |
| **Equation-numeric solver (add/sub/mul + maxmodmin)** | Same as cryptarithm but digits known → 550/594 guess (~93%). | §2 equation | **Medium-High** | **Yes — re-check our EQ premise** (4th refutation) | Medium |
| **Heavy bit data over-weighting** | bit CV is fragile to any mix change → 69%/66% of tokens were bit. | §3 final decisions | **High (negative lesson)** | **Yes — protect bit when scaling data** | Low |
| **Targeted hallucination subsets** | Synthetic subsets fixing common LoRA failures (`student→sent`, `clever→letter`) and repetitiveness. | §3.1 | **Medium** (cipher robustness) | **Yes** | Low |
| **Tinker for fast late-stage adapters** | Used Tinker to train adapters much faster late in the competition. | §Overall | **Low-Medium** (velocity) | **Maybe** (tooling) | Low |

## Provenance / attribution
- **Built on @huikang OPP** (numeral/unit/gravity/cipher solvers reused ~unchanged; baseline reasoners). Tools: **Unsloth**, **Tinker**, Kaggle / Google Cloud G4.
- **Novel to LB6 (vs prior art and LB1/LB3/LB5):** the **per-domain LB probing via DUMMY masking** and the explicit **full-train-as-validation** regime; the documented **bit-data fragility** trade-off and the resulting **selection regret**.
- **Cross-writeup note:** hex arithmetic matches LB1/LB3's HEX successes but **conflicts with LB5's "encoding broke the model"** — likely tokenization granularity (validate before adopting).
