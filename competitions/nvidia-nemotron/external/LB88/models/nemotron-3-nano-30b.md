# Base model — Nemotron-3-Nano-30B

- LoRA adapter (rank ≤ 32), vLLM eval (temp=0, 7680-token budget). LB88 used the public "LB 0.85" Unsloth/Tinker notebook lineage + @huikang OPP reasoner (unchanged).
- LB88 stability tweaks: **gradient clipping 1.5** (vs public 1e9), **per-character synthetic tokens** for cryptarithm. Exact rank/LR `unknown` (see `../LB92/`).
- Not downloaded (weights ≫ 20 MB).
