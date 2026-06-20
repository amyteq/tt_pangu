# Base model — Nemotron-3-Nano-30B

- Competition base model; submission = LoRA adapter (rank ≤ 32), loaded with vLLM (temp=0, 7680-token budget).
- Mamba-2 / MoE SSM (no standard attention → no Flash-Attention/XFormers; RTX PRO 6000 sm_120 makes causal-conv1d setup hard).
- **LB5 finding: Unsloth + 4-bit quantization + packing BREAKS Nemotron** (~100K examples, no learning); @huikang's trainer (no quant/packing) works. **DoRA** also unusable (vLLM unsupported; DoRA→LoRA conversion lossy).
- Not downloaded (weights ≫ 20 MB).
