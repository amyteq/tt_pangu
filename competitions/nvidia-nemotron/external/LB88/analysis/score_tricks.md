# LB88 / 88th Place — Score-improvement tricks

> Evidence cites `../writeup/lb88-writeup.md` (= `temp/LB88.pdf`). **Same writeup as LB92** — see `../LB92/analysis/` for the prior pass. "reusable by us" judged vs our repo.

| trick | description | evidence | likely impact | reusable by us? | difficulty |
|---|---|---|---|---|---|
| **Statistics-matched synthetic + gap QC loop** | Generate from train.csv stats (char freq, numeric ranges, transform distributions); train-on-synth/eval-on-both; the gap reveals generator flaws → fix iteratively. Final 2.5:1 synth:original. | §Overview 2 | **High** | **Yes — fixes our "synthetic dilutes"** | Medium |
| **Per-character tokenization (symbol categories)** | Synthetic tokens force 1 char = 1 token (cryptarithm BPE-merge fix). | §Tokenization trick | **Medium-High** | **Yes — novel, untried lever on our symbol weak spot** | Low-Medium |
| **Gradient clipping 1.5** | Public used 1e9 → instability / submission variance; clip at 1.5. | §Additional | **Medium** (variance) | **Yes — cheap A/B vs our 1e9-off** | Low |
| **"Don't lose solvable problems" framing** | Optimize faithful reproduction of an 87.8% reasoner, not harder problems. | §Overview 1 | **Medium (framing)** | **Yes — = our T12 anti-dilution** | n/a |
| **Longer training on hard tasks** | Longer training improved loss, esp. hard tasks. | §Overview 2 | **Low-Medium** | **Yes** | Low |
| **RL (SimPO/ORPO)** (negative) | chosen=reasoner, rejected=temp-1.3 samples; chosen prob rose but rejected barely fell (too similar) → dropped. | §What didn't work | **Negative** | **Avoid** (cf. LB5 pseudo-GRPO) | High |
| **Solving new bit/cryptarithm** (negative) | Search too big for the LLM token budget; Claude Fable 5 couldn't build a strong reasoner. | §What didn't work | **Negative** | Use LB1/LB3 structure instead | High |

## Provenance / attribution
- Built on **"End-to-end finetuning for LB 0.85"** + public 0.85 notebooks + **@huikang OPP reasoner** (unchanged).
- **Novel:** statistics-matched-synthetic + gap QC, per-character tokenization, grad-clip 1.5. (Same as LB92.)
- **Cross-writeup convergence:** RL fails here (SimPO/ORPO) and in LB5 (pseudo-GRPO) — chosen/rejected too similar; cryptarithm/bit "wall" they chose not to attack (cf. LB5/LB6/LB10/LB13).
