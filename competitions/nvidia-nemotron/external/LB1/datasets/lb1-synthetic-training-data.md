# LB1 synthetic training data (attached artifact)

- LB1 generated synthetic problems **programmatically** (NOT LLM-authored) from `train.csv` statistics, attached
  rule-based-solver traces, and trained SFT.
- Volume: **main 220,000 samples / 890.1M tokens**; **extra 140,000 / 590.7M tokens** (extra run processed ~104k).
  Per-category (main / extra samples): bit 40k/50k, equation 10k/10k, cryptarithm 120k/40k, cipher 20k/10k,
  numeral 10k/10k, unit 10k/10k, gravity 10k/10k. Validation = 15% train split (1,424 samples).
- The training data was attached to the writeup as a non-code artifact. **Not downloaded** (≫ 20 MB; JS-gated; out of scope).
