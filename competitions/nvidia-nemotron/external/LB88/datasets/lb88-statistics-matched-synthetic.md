# LB88 statistics-matched synthetic data

- Generated from train.csv statistics: **character frequencies, numeric ranges/distributions, transformation-method distributions**. Arbitrary `rule_found` samples.
- **QC loop:** train on synthetic, evaluate on synthetic AND original; the accuracy gap reveals generator flaws → fix iteratively. Final **synthetic : original = 2.5 : 1** (synthetic first, then original).
- **Per-character synthetic tokens** for cryptarithm (1 char = 1 token, fixing BPE merges).
- Not downloaded (notebooks JS/auth-gated). Same as LB92.
