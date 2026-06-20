# LB5 final LoRA adapter (iterative model soup)

- rank 32 / alpha 32, LR 1e-4→2e-4, grad_clip 1.0, linear schedule; @huikang trainer (no quant/packing).
- Produced by 3 phases over 15 iterations: (1) multi-round SFT, (2) **LoRA averaging regularization** (average before/after each step), (3) **iterative model soup** (train 3 models from one checkpoint, average). ~2B tokens total.
- Chosen submission: 88.8 public / 89.6 private (most stable, 3/5 times). Best unselected: **90.0 private**.
- Final model is in a linked Kaggle dataset; **not downloaded** (≫ 20 MB; JS/auth-gated).
