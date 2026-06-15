# Strategy — nemo

> English canonical. Original Chinese discussion preserved in `tracking_zh.md` / `notes_zh.md` and issue #86.

## Current direction
**Hold the best score (0.86, `nemo-merge-soup`) to close** (deadline 2026-06-15 23:59 UTC; **quota 5/5
used today → 0.86 is locked**). The 0.85 v14 ceiling was broken by an SVD **model-soup** of three
*comparable + complementary* 0.85 adapters (v14 replay + c1 verified-solver-CoT + b1 cryptarithm-synth →
**0.86**). Post-competition work tracked in `tasks.md` (top picks: T12 local metric, v11 self-distillation,
GRPO/RL, KCA-core YAML).

## Open discussions
> All D1–D9 from issue #86 were **confirmed 2026-06-12** (see `tracking.md` Table 1). None are still open;
> the last-roll question is resolved (the soup merge ran and won).

## Hypotheses
- **H1 (validated):** faithful public replay recipe (CCE + MoE tying + lm_head/Mamba LoRA + seq8192 +
  huikang corpus + replay-math) is the dominant lever (0.67→0.85). Evidence: T10.
- **H2 (refuted):** category-weighted cryptarithm synth lifts total accuracy — single-category gains did
  not transfer; ~24% synth share diluted other categories (v15 0.84). Low-dose b1 (~9%) recovered to 0.85.
- **H3 (refuted then refined):** weight-space SVD merge of **strong+weak** adapters beats the strongest —
  no, it dilutes (T7 0.82). **H3′ (validated):** a soup of **comparable + complementary** adapters DOES
  beat each member (soup 0.86) — the model-soup result (cf. Model Soups / LoRA Soups, `references.md`).
- **H4 (untested):** rejection-sampling self-distillation (v11) or RL (GRPO/PPO) could add headroom —
  never run; **post-competition** (see `tasks.md` + `research.md`).

## Rejected ideas
- v6: loss over prompt+padding (no response-only masking) → 0.44.
- ctx2k: seq2048 right-truncation destroyed the `\boxed{}` supervision tail → 0.42.
- T7: multi-adapter SVD merge (strong+**weak**) → 0.82; the strong+weak form is closed (but the
  comparable+complementary **soup** form won → 0.86).
- T11: ~24% cryptarithm synth dose → 0.84; de-prioritized (single-category ≠ total). Low-dose retries
  b1 0.85 / b2 0.84 / c2 0.83 tied-or-trailed; only the soup exceeded v14.

## Background analysis (zh source: work/00.nemo.md)
The competition is **hidden-rule generalization**, not memorization. Hardest categories: bit-manipulation
and equation/symbol transforms. Ideas A–F (rule-solver distillation, answer+CoT mixing, per-category
solvers/generators, bit-function enumeration, two-track equation handling, per-category local CV) are
recorded in `notes_zh.md`; most were superseded by the replay-recipe win. See also `insights.md`.
