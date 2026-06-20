# Base model — NVIDIA-Nemotron-3-Nano-30B-A3B-BF16

- The single base model (30B MoE, ~3B active). LoRA adapter (rank ≤ 32), vLLM eval (temp=0, 7680/8192-token budget).
- LB10 LoRA: rank 32, **alpha 128 (alpha/r=4)**, dropout 0; targets q/k/v/o + in/out + up/down_proj + lm_head; LR 2e-4 linear; 2 epochs; eff batch 32.
- Not downloaded (weights ≫ 20 MB).
