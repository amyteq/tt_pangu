# Strategy — nemo

> English canonical. Original Chinese discussion preserved in `tracking_zh.md` / `notes_zh.md` and issue #86.

## Current direction
**Hold the best score (0.85, `nemo-replay-v14`) to close** (deadline 2026-06-15 23:59 UTC). The faithful
replay of the public 0.86/0.87 recipe is our ceiling with current levers; two attempts to exceed it both
regressed (T7 merge 0.82, v15 cryptarithm synth 0.84). Remaining upside is low and high-risk.

## Open discussions
> All D1–D9 from issue #86 were **confirmed 2026-06-12** (see `tracking.md` Table 1). None are still open.
> The only live question is the optional last-roll variant below.

### D001: optional last-roll before the deadline
- status: open (user-decides)
- context: ~1.3 days left; v14=0.85 is banked; LB takes the max so downside is bounded.
- options: (a) hold 0.85; (b) half-dose cryptarithm-only synth (~800 ex, ~8%) to cut dilution.
- current leaning: **hold** — by the observed pattern, the variant is expected to land ≤0.85.
- evidence: issue #86 comment 4.
- follow-up: none unless the user requests the variant.

## Hypotheses
- **H1 (validated):** faithful public replay recipe (CCE + MoE tying + lm_head/Mamba LoRA + seq8192 +
  huikang corpus + replay-math) is the dominant lever (0.67→0.85). Evidence: T10 / issue #86 comment 2.
- **H2 (refuted):** category-weighted cryptarithm synth lifts total accuracy — single-category gains did
  not transfer; ~24% synth share slightly diluted other categories. Evidence: T11 / comment 4.
- **H3 (refuted):** weight-space SVD merge of strong+weak adapters beats the strongest member — dilution,
  not enhancement. Evidence: T7 / comment 3.
- **H4 (untested):** rejection-sampling self-distillation (v11) or Unsloth seq8192 (v12) could add headroom —
  never run (out of budget; v14 replay made them lower-priority).

## Rejected ideas
- v6: loss over prompt+padding (no response-only masking) → 0.44.
- ctx2k: seq2048 right-truncation destroyed the `\boxed{}` supervision tail → 0.42.
- T7: multi-adapter SVD merge (strong+weak) → 0.82; route **closed**.
- T11: ~24% cryptarithm synth dose → 0.84; de-prioritized (single-category ≠ total).

## Background analysis (zh source: work/00.nemo.md)
The competition is **hidden-rule generalization**, not memorization. Hardest categories: bit-manipulation
and equation/symbol transforms. Ideas A–F (rule-solver distillation, answer+CoT mixing, per-category
solvers/generators, bit-function enumeration, two-track equation handling, per-category local CV) are
recorded in `notes_zh.md`; most were superseded by the replay-recipe win. See also `insights.md`.
