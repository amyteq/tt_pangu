# NVIDIA Nemotron Model Reasoning Challenge (nemo)

> Canonical language: **English**. Original Chinese tracking material preserved in `tracking_zh.md` /
> `notes_zh.md` and in GitHub issue #86. Aliases: `nemo`, `nemotron`.
> Kaggle slug: `nvidia-nemotron-model-reasoning-challenge`.

## Status snapshot
- status: **active** (deadline **2026-06-15 23:59 UTC**, imminent)
- phase: submission (closing)
- current objective: **hold the best score (0.85, v14 replay) to close**; only low-cost upside left
- best known local/CV: per-kernel held-out only (no single canonical CV); see `submissions.md`
- best known LB/public: **0.85** own real-training (`nemo-replay-v14`); raw account max **0.86** (2026-05-15 public-fork, not own training); top **~0.90**, base ~0.47 (refreshed 2026-06-14)
- current blocker: 0.85 appears to be the ceiling with current levers — two attempts to beat it
  (T7 SVD merge 0.82, T11 v15 cryptarithm synth 0.84) both regressed
- next task: hold 0.85; optional half-dose cryptarithm-only synth (expected ≤0.85)

## Key links
- rules: ./rules.md
- strategy: ./strategy.md · zh: ./strategy_zh.md
- tasks: ./tasks.md
- tracking (issue #86 tables, EN): ./tracking.md · zh: ./tracking_zh.md
- submissions: ./submissions.md
- bugs: ./bugs.md
- references: ./references.md
- insights: ./insights.md
- experiments: ./experiments/ (kernels v10/v14/v15, t7 svd-merge, synth generator)
- postmortem: ./postmortems/2026-06-14-context-consolidation.md
- historical hub: GitHub issue #86 (kept open for history; do not use for new status)

## Current top 3 priorities
1. Hold the 0.85 (`nemo-replay-v14`) entry through the 2026-06-15 deadline.
2. (Optional, low-cost) half-dose cryptarithm-only synth variant (~8%) — expected ≤0.85; user decides.
3. Post-competition: localize the official metric + min-logprob hard-validation set (T12); avoid eval-truncation regressions.

## Latest update
- date: 2026-06-14
- source: issue #86 (comments 2–4), PRs #90/#94/#95
- summary: v14 replay reached **LB 0.85** (+0.18 over prior best 0.67). Two follow-ups to exceed it
  both regressed: T7 multi-adapter SVD merge → 0.82, T11 v15 cryptarithm synth → 0.84. Recommendation:
  hold 0.85 to close.
