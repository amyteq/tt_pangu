# LB25 / 25th Place — Score-improvement tricks

> Evidence cites `../writeup/lb25-writeup.md` (= `temp/LB25.pdf`). "reusable by us" judged vs our repo (notes.md / equation-frontier.md / bugs.md).

| trick | description | evidence | likely impact | reusable by us? | difficulty |
|---|---|---|---|---|---|
| **Fix the boxed-prompt eval bug** | The validation prompt didn't box the answer (but submission did) → local eval systematically wrong; fixing it realigned validation with the LB. | change #1 | **High** (correct signal) | **Yes — = our B4/T13 + INS-002**; align local eval to grader exactly | Low |
| **equation_numeric reversal symmetry** | Either both inputs+outputs are reversed or neither (per problem) → halve the equation search. | change #2 | **Medium-High** | **Yes — re-check EQ premise** (earliest evidence equation has structure) | Low-Medium |
| **Easy-category synthetic (cipher/unit/gravity/numeral)** | Synthetic to guarantee ~100% on easy categories. | change #3 | **Medium** | **Yes** | Low |
| **Cipher-prefix synthetic (spelling)** | Nemotron spells poorly → synthetic data targeting cipher prefixes. | change #4 | **Medium** (cipher robustness) | **Yes** (cf. LB6 targeted subsets) | Low |
| **Reorganize bit-manipulation CoT** | Restructure the bit CoT. | change #5 | **Medium** (bit) | **Yes** (cf. LB1/5/6/10/13 bit redesigns) | Medium |
| **Submission selection under noise** | 0.872/0.868/0.864 across 15 subs — selection is a score determinant under temp=0 non-determinism. | §Result | **High (meta-lesson)** | **Yes** — trust LB aggregate; don't over-hedge (INS-002) | n/a |

## Provenance / attribution
- LB25 **is** the Progress-Prize baseline lineage by @huikang (`tonghuikang/nemotron`) that the field (and our v14) built on. These are *improvements on his own* submission.
- **Cross-writeup convergence:** the **equation reversal symmetry** here is the earliest of seven independent confirmations (LB1/LB3/LB5/LB6/LB10/LB13) that equation is per-problem-structured, **not a global cipher**; **cryptarithm unsolved** even by huikang confirms it as the top-end lever (LB1 signature catalog / LB3 two-stage).
