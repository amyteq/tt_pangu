# Depth 1 — direct references from the 3rd-place writeup (budget ≤10; 6 followed)

LB3 acknowledges four prior works by handle; URLs resolved via prior LB1 research + WebSearch.

| # | handle | what | URL | type | fetchable | summary |
|---|---|---|---|---|---|---|
| 1 | llkh0a | starter notebook (trivial + cipher traces reused) | Kaggle code by `llkh0a` (slug not indexed) | notebook | JS-gated | YS-L's entry point; final model still uses its traces for some categories |
| 2 | huikang / tonghuikang | progress-prize solution + **CCE manual training loop** | https://github.com/tonghuikang/nemotron | repository | YES | LB3 uses the CCE training loop ("amazing, not talked about enough") |
| 3 | huikang | progress-prize discussion | https://www.kaggle.com/.../discussion/689915 | discussion | JS-gated | NO_CONTENT |
| 4 | youkinasa | pattern-matching / multi-example **intersection** idea | https://www.kaggle.com/.../discussion/688461 | discussion | JS-gated | LB3's cryptarithm intersection strategy is inspired by this |
| 5 | kemshim | symbolic equation solver for cryptarithm | Kaggle discussion (JS-gated) | discussion | JS-gated | LB3 borrowed these ideas |
| 6 | (provided) | local PDF | `temp/LB3.pdf` | writeup | YES | depth-0 body |

**Attribution conclusion:** LB3 builds on llkh0a (trivial+cipher traces), huikang (CCE loop, per-bit solver, backtracking DFS), youkinasa (multi-example intersection), kemshim (symbolic solver). **Novel to LB3:** the **two-stage memorize→execute training** and the **CSP intersection→anchor→bounded-backtracking** cryptarithm solver. (Hex bit compression appears in both LB1 and LB3 independently.)
