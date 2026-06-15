# Insights — nemo

## Competition-specific insights
- **Faithful replay of the public 0.86/0.87 recipe is the single biggest lever** (0.67→0.85): CCE +
  MoE 128-expert weight tying + LoRA on `lm_head`/`in_proj`/`out_proj` + seq8192 + huikang recording-order
  corpus + replay-math answer tokens. Evidence: issue #86 T10 / comment 2.
- **A model-soup of comparable+complementary adapters is the lever that beat the recipe** (0.85→**0.86**):
  the SVD soup of v14 + c1 (verified solver-CoT) + b1 (cryptarithm synth) — three 0.85 same-base fine-tunes
  on *different* data — exceeded each member. Single add-on runs only tied/trailed (b1 0.85, c1 0.85, b2 0.84,
  c2 0.83), and the strong+weak merge (T7) and high-dose synth (v15) regressed (0.82 / 0.84). Evidence:
  tracking.md; INS-004; cf. Model Soups / LoRA Soups (`references.md`).
- **Single-category gains ≠ total-score gains**: cryptarithm 8%→71% single still left total ~0.86.
  Evidence: issue #86 T11 / comment 4.
- **CoT supervision must land at the sequence tail and survive truncation** (`</think>\n\boxed{}`);
  right-truncation at small seq destroys it (ctx2k → 0.42). Evidence: issue #86 T2 / comment 0.

- **response-only loss masking is the key to CoT SFT**: training the loss over prompt+padding (v6) collapsed to 0.44; masking the prompt (labels=-100, response-only) recovered it (v7 0.65). Evidence: `bugs.md` B2 / issue #86 comment 0.
- **CoT traces must precompute every intermediate value (no inline arithmetic) and end with a finality line**: v10's short rule-traces made greedy reasoning shallow (0.59); v15's generator fixed this (CoT-answer consistency 1930/1930). Evidence: issue #86 T4 / T11; `work/00.nemo.md` ideas A/B.

## Potentially reusable insights

### INS-001: push-time static lint + single-example fail-fast preflight
- type: rule
- confidence: high
- evidence: `kernels/README.md`; issue #86 (F821 / `.shape` each cost ~2h GPU)
- transfer scope: any GPU kernel / long training competition
- status: candidate (logged in `_shared/skill-candidates.md`)

### INS-002: eval harness must mirror the official metric (decode length + extractor)
- type: anti-pattern
- confidence: high
- evidence: issue #86 T12/T13 (EVAL_MAX_NEW 512→7680; port official extract/verify)
- transfer scope: any hidden-test LLM/eval competition
- status: candidate
- notes: misaligned local eval gives misleading scores (cf. orbit-wars self-play vs ladder).

### INS-003: weight-space adapter merge only among comparable, complementary adapters
- type: fact
- confidence: medium→high
- evidence: T7 strong+weak SVD merge regressed (0.82); refined by INS-004
- transfer scope: multi-checkpoint LoRA/adapter ensembling
- status: validated (this competition)

### INS-004: model-soup of comparable, complementary same-base fine-tunes beats each member
- type: technique
- confidence: high
- evidence: v14 (0.85, replay) + c1 (0.85, verified solver-CoT) + b1 (0.85, cryptarithm synth) → SVD soup
  (weights 0.4/0.3/0.3, rank-32) = **0.86** new best; each trained on the SAME base, DIFFERENT data.
- transfer scope: any LoRA/PEFT competition where you can train several diverse same-base fine-tunes.
  Recipe: train N≥3 diverse fine-tunes near the same loss basin → average their LoRA deltas (weighted) →
  SVD-truncate back to the rank cap. Members must be *comparable* (similar score) AND *complementary*
  (different data/seed); strong+weak (INS-003) dilutes.
- literature: Model Soups (2203.05482), LoRA Soups / AdapterSoup (`references.md`).
- status: validated (this competition); promote to `_shared/skill-candidates.md`.
