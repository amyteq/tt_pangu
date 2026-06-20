# LB13 LoRA adapter (3-stage SFT)

- Single LoRA trained in **3 stages with decreasing LR**: (1) 9,277 / 2ep / 2e-4 linear (align); (2) 9,277 / 1ep / 2e-5 cosine (smooth); (3) 11,315 / 1ep / 5e-6 cosine (upsample bit + cryptarithm to fix residual trace errors).
- Aggressive/overfit-prone by design — goal is better CoT trace generation, not zero-shot reasoning.
- No model merging used. Not downloaded (weights ≫ 20 MB; not publicly linked).
