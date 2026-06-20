# Base model — Nemotron-3-Nano-30B

- Competition base model; submission = LoRA adapter (rank ≤ 32), loaded with vLLM (temp=0, 7680-token budget).
- Mamba-2 / MoE-128 SSM (per our notes.md). LB3 LoRA targets q/k/v/o + up/down + in/out_proj + lm_head (manual LM-head LoRA), **MoE tie weights OFF** (LB3 found this better — opposite of our v14 MoE-128 tying).
- Not downloaded (weights ≫ 20 MB).
