# Depth 1 — direct references from the 6th-place writeup (budget ≤10; 7 followed)

| # | ref | what | URL | type | fetchable | summary |
|---|---|---|---|---|---|---|
| 1 | @huikang OPP | baseline solvers (numeral/unit/gravity/cipher reused) + reasoners | https://github.com/tonghuikang/nemotron | repository | YES | the OPP baseline LB6 built on |
| 2 | @huikang | OPP discussion | https://www.kaggle.com/.../discussion/689915 | discussion | JS-gated | NO_CONTENT |
| 3 | LB6 bit trace | reasoning-trace example | Kaggle (linked) | code/trace | JS/auth-gated | bit-manipulation trace |
| 4 | LB6 cryptarithm trace | reasoning-trace example | Kaggle (linked) | code/trace | JS/auth-gated | cryptarithm trace |
| 5 | Unsloth | training framework | https://github.com/unslothai/unsloth | repository | YES | hypothesis testing on Kaggle/GCP G4 |
| 6 | Tinker | fast late-stage adapter training | (no URL in writeup) | tool | n/a | named only |
| 7 | (provided) | local PDF | `temp/LB6.pdf` | writeup | YES | depth-0 body |

**Attribution conclusion:** LB6 builds on @huikang OPP (reused easy-category solvers; bit/cryptarithm baselines). **Novel to LB6:** **per-domain LB probing (DUMMY masking)**, **full-train-as-validation**, the **template bit solver (hex + skips + ternary)**, the **DFS cryptarithm solver with reversed search**, and the documented **bit-data fragility / selection regret**.
