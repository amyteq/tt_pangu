# Depth 1 — direct references from the 1st-place writeup (budget ≤10; 8 followed)

The writeup cites prior work by name/handle (no inline hyperlinks survive PDF extraction); URLs resolved via prior research + WebSearch.

| # | handle | title | URL | type | fetchable | summary |
|---|---|---|---|---|---|---|
| 1 | @huikang / tonghuikang | Open Progress Prize repo | https://github.com/tonghuikang/nemotron | repository | YES | per-output-bit bit solver + backtracking cryptarithm DFS; the acknowledged starting point |
| 2 | @huikang | "Winning the Nemotron Progress Prize" (blog) | https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html | blog | YES (partial) | announcement; defers detail to discussion 689915 |
| 3 | @huikang | Open Progress Prize discussion / "Strategy to solve 85% of bit manipulation" | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915 | discussion | JS-gated | bit-manip strategy; LB1's direct bit starting point |
| 4 | @youkinasa | "A Pattern-Matching Approach to Solving Symbolic Arithmetic Puzzles" | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/688461 | discussion | JS-gated | precomputed operation table keyed by signature → LB1 turned it into a *memorized* catalog |
| 5 | @kemshim (+@MAJ0RT0M) | "Trying to improve cryptarithm — feedback welcome" | Kaggle competition discussion (JS-gated) | discussion | JS-gated | mul-pattern-table memorization; learnability-limit discussion |
| 6 | unslothai | Unsloth | https://github.com/unslothai/unsloth | repository | YES | LB1's SFT framework (2× faster, less VRAM); standard tool |
| 7 | OpenAI | Codex | https://openai.com/index/introducing-codex/ | documentation | 403 from sandbox | LB1 wrote all code with Codex; ideas were human |
| 8 | (provided) | local PDF | `temp/LB1.pdf` | writeup | YES | depth-0 body |

**Attribution conclusion:** LB1 builds on @huikang (bit per-output-bit solver, cryptarithm DFS, simple-category procedures) and @youkinasa (signature/operation-table viewpoint). LB1's own additions: HEX compression, the *memorized* signature catalog + candidate-count, the rule-sequence catalog + Hamming repair.
