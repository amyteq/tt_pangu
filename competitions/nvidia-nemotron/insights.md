# Insights — nemo

## Competition-specific insights
- **Faithful replay of the public 0.86/0.87 recipe is the single biggest lever** (0.67→0.85): CCE +
  MoE 128-expert weight tying + LoRA on `lm_head`/`in_proj`/`out_proj` + seq8192 + huikang recording-order
  corpus + replay-math answer tokens. Evidence: issue #86 T10 / comment 2.
- **Any "augmentation" on top of the clean replay recipe dilutes it** — T7 merge (0.82) and v15 cryptarithm
  synth (0.84) both regressed. Weight-space merge only helps among comparable, complementary adapters;
  strong+weak dilutes. Evidence: issue #86 comments 3–4.
- **Single-category gains ≠ total-score gains**: cryptarithm 8%→71% single still left total ~0.86.
  Evidence: issue #86 T11 / comment 4.
- **CoT supervision must land at the sequence tail and survive truncation** (`</think>\n\boxed{}`);
  right-truncation at small seq destroys it (ctx2k → 0.42). Evidence: issue #86 T2 / comment 0.

## Potentially reusable insights

### INS-001: push-time static lint + single-example fail-fast preflight
- type: rule
- confidence: high
- evidence: `experiments/kernel/README.md`; issue #86 (F821 / `.shape` each cost ~2h GPU)
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
- confidence: medium
- evidence: issue #86 T7 / comment 3 (strong+weak SVD merge regressed)
- transfer scope: multi-checkpoint LoRA/adapter ensembling
- status: validated (this competition)
