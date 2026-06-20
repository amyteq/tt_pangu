# Depth 1 — direct references from the 5th-place writeup (budget ≤10; 7 followed)

| # | handle/ref | what | URL | type | fetchable | summary |
|---|---|---|---|---|---|---|
| 1 | @huikang / tonghuikang | CoT generator + byte-level bit + training notebook | https://github.com/tonghuikang/nemotron | repository | YES | LB5 modified this trainer (LR + synthetic data + stopper); base for bit/cipher/gravity/conversion/cryptarithm CoT |
| 2 | @huikang | progress-prize discussion | https://www.kaggle.com/.../discussion/689915 | discussion | JS-gated | NO_CONTENT |
| 3 | @donaldgalliano | per-bit 100%-solve claim | Kaggle discussion (JS-gated) | discussion | JS-gated | LB5 **rejected** it (too many bit-level transforms fit/diverge → not generator-intended) |
| 4 | @citerne | Kaggle CLI tutorial | Kaggle discussion (JS-gated) | discussion | JS-gated | the Kaggle CLI training workflow LB5 relied on |
| 5 | LB5 master notebook | Kaggle (linked) | notebook | JS/auth-gated | phases 1–3 compiled into one notebook |
| 6 | LB5 final-model dataset | Kaggle (linked) | dataset | JS/auth-gated | final LoRA adapter (≫20 MB; not downloaded) |
| 7 | (provided) | local PDF | `temp/LB5.pdf` | writeup | YES | depth-0 body |

**Attribution conclusion:** LB5 builds on @huikang (trainer, byte-level bit, several CoTs) and references @donaldgalliano (rejected per-bit idea) + @citerne (Kaggle CLI). **Novel to LB5:** the **no-leakage infinite generator → private-tracking CV**, **iterative LoRA averaging as a regularizer**, and the **ternary byte-level bit solver with memorized continuations**. LB5 **fails** cryptarithm (the LB1/LB3 lever).
