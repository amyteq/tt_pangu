# LB6 synthetic datasets (two final)

- Distribution-matched synthetic (full train.csv reserved for validation). Per-domain stats: example counts; gravity/unit empirical parameter distributions; cipher unseen-char/word/sentence structure; bit per-template shift/equation/input variation (more 3-atom problems); cryptarithm fixes op-set/reversal and **rerolls digit mappings until the reasoner solves under the token limit**. Targeted subsets fix hallucinations (`student→sent`, `clever→letter`) and repetitiveness.
- **~0.25B tokens (6th private):** bit 69% of tokens; gravity/unit/numeral perfect, cipher ~98.5%, bit & equation ~92%, cryptarithm ~17%.
- **~0.5B tokens (potential 2nd-3rd):** bit 66%; doubled cryptarithm (train cryptarithm solved 150→241); but the bit-CV drop was under-estimated → not shipped.
- Not downloaded (linked attachments JS/auth-gated; out of scope).
