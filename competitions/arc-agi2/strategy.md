# Strategy — ARC-AGI-2

> English canonical. Human-facing Chinese walkthrough of the same ideas is in `overview_zh.md` §挑战/§提分技术.
> Status: **research only** — nothing below is validated yet. Each item is a hypothesis to test, not a claim.

## Current direction (proposed)
Land a **TTT baseline** in the NVARC/ARChitects family (target ≈ the 2025 floor of ~24%), wrapped in a
**local pass@2 eval harness** so we can iterate without spending Kaggle submits. Then push two orthogonal
levers: (a) **candidate selection** for pass@2, (b) **better priors** (synthetic data + DSL/program
verification) for the compositional / sequential tasks ARC-AGI-2 added. Keep a publishable research log —
the **Grand Prize ($275K) is writeup-scored and guaranteed**, so it's the highest-EV target given that 85%
(Bonus) is likely out of reach within the Kaggle envelope.

## Hypotheses (to test, in priority order)
- **H1 — TTT is still the dominant Kaggle lever.** Per-task fine-tune on augmented demos + augmentation-
  inverted voting reproduces ~20–24%. *Test:* reproduce NVARC/ARChitects recipe on a ≤4B base, score on
  the 120 public-eval tasks locally. **Highest leverage; do first.**
- **H2 — Candidate selection is underexploited and cheap.** Because the metric is pass@2, a good
  *selector* (augmentation-consistency vote / demo-fit re-scoring of N candidates) lifts score with no extra
  training. *Test:* generate N≥8 candidates, compare "top-2 by vote" vs naive top-2.
- **H3 — Synthetic ARC-2-like data closes the compositional gap.** A generator producing multi-rule /
  contextual / sequential tasks (re-arc style, extended) as pretraining raises the TTT ceiling on the new
  task types. *Test:* pretrain on synthetic, measure delta on the public-eval subset that is non-trivial.
- **H4 — A hybrid neural-guided DSL verifier beats pure-neural on the "executable" subset.** For tasks
  expressible as short grid-transform programs, an LLM proposes programs and a verifier checks exact demo
  fit (zero false positives). *Test:* measure coverage on public eval; only worth it if it adds tasks TTT misses.
- **H5 — Efficiency (small model + TTT) ≥ big ensemble within $10K/12h.** *Test:* score-vs-cost curve across
  model sizes; pick the knee, not the max.

## Ideas to try (ranked by expected value × cheapness)
1. **Local eval harness + task viewer** (prereq for everything; see `tasks.md` T1).
2. **TTT baseline reproduction** (H1) — the floor; substrate for all later work.
3. **Augmentation set + inverted-vote selection** (H2) — cheap pass@2 gain.
4. **Synthetic data generator** for the new ARC-2 task families (H3) — the compositional-gap lever.
5. **Per-task-type routing / specialization** — detect task family, route to the best solver/adapter.
6. **Neural-guided DSL search with exact verifier** (H4) — high precision on the executable subset.
7. **Recursive-refinement model (TRM-style)** — the efficiency-frontier architecture NVARC used.

## What to avoid (lessons carried from nemo + ARC-2 design)
- **Don't gate on a leaderboard you can't see** — build the local pass@2 harness first (nemo lesson:
  CV/LB divergence). Verify it reproduces a known public-notebook score before trusting it.
- **Don't reach for brute-force search** — ARC-2 removed the tasks where it works, and the $10K/12h ceiling
  kills it anyway.
- **Don't assume API-LLM scores transfer** — the 37–85% frontier numbers use internet + unlimited compute;
  the scored Kaggle run has neither.
- **Don't over-dose synthetic data** — nemo H2 showed a single-family over-dose dilutes the rest; keep
  generated mixes balanced and measure per-family deltas, not just the aggregate.
- **One meaningful change at a time**; record hypothesis → change → seed → local pass@2 → decision (per
  `docs/experiment-discipline.md`) in `tracking.md`.

## Two prize paths (be explicit about which we're optimizing)
- **Bonus $150K @ 85%** — likely infeasible in-Kaggle this year; treat as aspirational, not the plan.
- **Progress $275K (rank, top-8)** — realistic if we beat ~24%; the accuracy game.
- **Grand $275K (writeup, guaranteed payout)** — best EV. Optimize the *research narrative*
  (theory/novelty/universality) alongside accuracy from day one; keep `tracking.md` paper-grade.

## Decision gates (autonomy note)
This is **research phase** — no Kaggle env, account, or `kca-arc.yaml` exists yet. Before any external
push/submit, create the per-competition autonomy config and confirm the human wants live runs (see
[[project_kca_autonomy_model]]). Final-week promotion near the Nov 2 deadline is human-gated regardless.
