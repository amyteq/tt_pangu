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

### INS-005: competitor-writeup *methods* reproduce; their *LB* often doesn't — and three failure modes to pre-screen
- type: anti-pattern / screening checklist
- confidence: high (3 independent borrows, all negative/neutral)
- evidence: 2026-06-20 LB25/LB80/LB92 borrow campaign — v16-evalfix 0.832/0.828, v17-discovery 0.840/0.848, v18-stable 0.844/0.848; none beat the held 0.86 soup/eq-aug. `submissions.md` §LB25/LB80/LB92, `tracking.md`.
- the three pre-screens (apply BEFORE spending a GPU session on a borrowed lever):
  1. **Measurement vs model.** A lever that fixes *local↔grader eval parity* (LB25 LEVER 1) corrects your *prediction* of the LB, not the LB itself — it cannot move a score the grader already computes correctly. Worth doing for trustworthy local validation; worth **zero** LB.
  2. **Submission-format feasibility.** This comp submits ONLY the LoRA adapter; the grader uses the FIXED base model + base tokenizer. So **vocab-changing levers (per-char tokenization / `add_tokens` + resize, LB92 LEVER 2) are infeasible** — added tokens/embeddings never reach inference. Check what the grader actually loads before implementing.
  3. **Dilution is the default outcome** for added SFT data (bit CoT, synth, discovery CoT) even at ≤15% verified dose (v16 −0.018; b1/b2/c1/c2/v15 before it). Adding rows to an already-near-ceiling adapter regresses more often than it helps; require a local gate you can actually run, or treat the submission itself as the (cheap, late-window) gate.
- equation corollary: the cipher IS crackable (per-operator digit-string rules; `versions/lb1-v1/rules24.py` = 95% numeric-deduce), but cracking the *plaintext-digit* subset doesn't lift the LB — the ~82% glyph-ciphered queries need a joint cipher+op crack, and even a perfect offline solver is a *training-data* method (base ~0.47), GPU-gated. Equation stays the wall.
- transfer scope: any code-/adapter-submission competition where you're tempted to port a top writeup's lever. Pre-screen 1–3; default-distrust SFT-data additions; trust the LB aggregate over hard-tail proxies (INS-002).
- status: validated (this competition).
