# Depth 1 — direct references (budget ≤10; 5 followed)

| # | ref | what | URL | type | fetchable | summary |
|---|---|---|---|---|---|---|
| 1 | base notebook | "End-to-end finetuning for LB 0.85" | Kaggle (linked) | notebook | JS/auth-gated | the base |
| 2 | notebook | "Training with Unsloth to Achieve 0.85 LB" | Kaggle (linked) | notebook | JS/auth-gated | influence |
| 3 | notebook | "Tinker submission notebook" | Kaggle (linked) | notebook | JS/auth-gated | influence |
| 4 | @huikang OPP | reasoner (unchanged) | https://github.com/tonghuikang/nemotron | repository | YES | the 87.8% oracle baseline |
| 5 | prior archive | LB92 (same writeup) | `../LB92/` | archive | YES | figures + prior analysis |

**Attribution conclusion:** LB88 (=LB92) builds on the public 0.85 notebooks + @huikang OPP reasoner. **Novel:** statistics-matched synthetic + gap QC, per-character tokenization, grad-clip 1.5.
