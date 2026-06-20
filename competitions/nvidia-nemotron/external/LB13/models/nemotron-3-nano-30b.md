# Base model — Nemotron-3-Nano-30B

- Competition base model; LoRA adapter (rank ≤ 32), vLLM eval (temp=0, 7680-token budget).
- LB13 LoRA: rank/alpha 32/32, dropout 0; targets q/k/v/o + in/out + up/down_proj (**no lm_head** — vLLM ignores it anyway). 3-stage decreasing-LR SFT (2e-4 → 2e-5 → 5e-6); eff batch 32, AdamW.
- Not downloaded (weights ≫ 20 MB).
