# LB3 augmented training data

- Final mix **72,377 samples / 299.4M tokens**: cryptarithm 43,157 (59.6%, 48K augmented incl. 4K concat), bit 13,998 (19.3%; 3K swap + 3K formula ×2), cipher 4,418 (6.1%; +3K), numeric 4,076 (5.6%; +3K), **cryptarithm_pattern_drill 3,000 (4.1%)**, gravity/unit/numeral ~5%.
- **Augment by resampling originals** (change operands/symbols of existing problems) to preserve official-generator artifacts rather than free-generating. Cryptarithm = numeric problem → cipher-encrypt.
- Stage-1 drill corpus (44,136 examples / 159.3M tok) = pure `<RECALL_DOMAINS>`/`<RECALL_ROWS>` completions over all mul signatures, 16 packed per sample, request masked.
- Not downloaded (attachment; out of scope).
