# LB3 final LoRA adapter (two-stage)

- rank 32 / alpha 32, dropout 0.0, fp32. Produced by **two-stage training**: stage-1 memory adapter (drills, 25.2h, ~27.6K steps) → used as the **initial adapter** for stage-2 execution training (32.7h, 18,095 steps).
- Trained with huikang's CCE loop, effective batch size 4, LR 2e-4 linear, grad norm 10, seq 8192, seed 42, single GPU (~58 GPU-h total, ~4.6e8 tokens).
- **Private LB 0.900.** Not downloaded (weights ≫ 20 MB; JS-gated).
