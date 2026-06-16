# Final postmortem — NVIDIA Nemotron Model Reasoning Challenge (FINAL)

> **Status: FINAL — private LB released 2026-06-16.** Competition closed 2026-06-15 23:59 UTC.
> **Own-work best: public 0.86 → private 0.85** (soup). Both team accounts finished **0.85 private**.
> Sources: `submissions.md`, `tracking.md`, `insights.md`, the 2026-06-14/15 postmortems; live Kaggle API.

## 1. Headline
- **Best own-work: 0.86 public → 0.85 private** — the 3-way SVD **model-soup** `v14(0.4)+c1(0.3)+b1(0.3)` (compliant own training, no repack). It was the **most robust 0.86** (only −0.01 public→private).
- Progression: base 0.47 → v5 0.61 → v7 0.65 → ctx4k 0.67 → **v14 replay 0.85** → **soup 0.86 (→0.85 private)**.
- The clean public-recipe replay (CCE + MoE-expert tying + lm_head/Mamba LoRA + seq8192 + huikang corpus + replay-math) was the single biggest lever (0.67→0.85); the soup added the last public +0.01.

## 2. Final selections & outcome
Two separate account entries (registered teammates; each selects 2). **Both finished 0.85 private.**
| Account | Pick 1 (priv) | Pick 2 (priv) | Final (max) | Verdict |
|---|---|---|---|---|
| harrysun2006 (`flyingfox`) | **soup 0.86→0.85** | v14 0.85→0.84 | **0.85** | soup dominated; v14 hedge correct (never needed — soup ≥ v14 on private). |
| firefly2006 | b1 0.85→0.84 | **b2 0.84→0.85** | **0.85** | the hedge *paid off*: b2 (lower public) was the **higher private** — selecting both captured 0.85. |

Public standing: `flyingfox` **rank 150/4350** (0.86 public, top ~3.4%); `firefly2006` 2013/4350 (0.85). Private top **0.92** (NullSira), public top 0.91, public median 0.85, 4350 teams. (Exact private rank not CLI-extractable — the downloadable board is the public one; our private *scores* are authoritative from the submissions API.)

## 3. Full results — public → private (own work)
| version | account | public | **private** | Δ | note |
|---|---|---:|---:|---:|---|
| **soup** | harry | 0.86 | **0.85** | −0.01 | best; most robust 0.86 (selected) |
| surgery scale_1.15 | harry | 0.86 | 0.84 | **−0.02** | **worst-aging 0.86** — the ×1.15 amplification *overfit* public |
| v14 | harry | 0.85 | 0.84 | −0.01 | replay; hedge pick (selected) |
| c1 | harry | 0.85 | 0.85 | 0.00 | verified solver-CoT — held |
| b1 | may | 0.85 | 0.84 | −0.01 | cryptarithm synth (selected) |
| v15 | harry | 0.84 | 0.84 | 0.00 | cryptarithm-weighted synth |
| **b2** | may | 0.84 | **0.85** | **+0.01** | cryptarithm+bit synth — best may private (selected) |
| c2 | harry | 0.83 | 0.83 | 0.00 | hard-cat solver |
| t7 merge | harry | 0.82 | 0.80 | −0.02 | strong+weak merge (dilution) |
| andy279 | may | 0.81 | 0.81 | 0.00 | external-teacher solver-CoT — regressed, flat |
| v11 self-distill | may | 0.80 | 0.82 | +0.02 | rejection-sampled CoT — recovered but sub-0.85 |
| ctx4k / v7 / v5 / v10 / v6 / ctx2k / identity | both | 0.67/0.65/0.61/0.59/0.44/0.42/0.47 | 0.66/0.66/0.66/0.64/0.45/0.46/0.52 | — | early line; weak models rose on private (regression to mean) |

## 4. What the private LB confirmed
- **The clean replay + comparable-complementary soup is the robust winner** (0.85 private). Public→private was well-correlated; no shake-up. The 0.85 ceiling was **replay/soup-driven, not equation-driven**.
- **Near-duplicates age worst.** Surgery (soup ×1.15) dropped −0.02 vs the soup's −0.01 — amplifying the LoRA overfit public. → **selection discipline vindicated**: best + a *diverse* hedge, never a duplicate (INS-005 confirmed on private).
- **The diverse hedge can win.** may's b2 (lower public) beat b1 on private; selecting two complementary members captured the better one — exactly the hedge rationale (don't pick the higher-public twin).
- **Every augmentation route under-delivered**: synth (v15/b1/b2 ≈ replay), solver-CoT (c1 held, c2 below), external-teacher (andy279 0.81), self-distill (v11 0.82) — all ≤ the plain replay/soup. "Augmentation dilutes the clean replay recipe / single-cat ≠ total" (B8) **held on private too**.
- **`equation` stayed unsolved** — no adapter cracked it; it is the documented path to >0.85 (see `equation-frontier.md`).

## 5. Reusable insights (validated, incl. on private)
- INS-001 push-time static lint + single-example fail-fast preflight.
- INS-002 mirror the official metric; but small local-eval gaps are **noise** (surgery +1/78 hard-val → 0.00 public, −0.02 private).
- INS-003 weight-space merge only helps among comparable+complementary adapters (t7 strong+weak −0.02 private).
- INS-004 model-soup of comparable+complementary members beats each member; **and is the most robust public→private** (soup −0.01).
- INS-005 post-hoc spectral surgery can't add missing capability and **overfits** (−0.02 private) — confirmed.
- INS-006 external-teacher / self-distill CoT dilutes a strong replay backbone (single-cat ≠ total) — confirmed.
- **INS-007 (new): for final-pick selection, prefer best + a *diverse* member over a higher-public *duplicate*** — at the top, public→private shrinks ~0.01–0.02 and duplicates age worse; a diverse hedge can out-score the public-best twin (b2 vs b1).
- Offline vLLM on Blackwell: aimo-3-utils-0171 + `--target`/PYTHONPATH/invalidate_caches (see `reference_vllm_offline_kaggle_blackwell`).

## 6. Final lesson
Faithful reproduction of the public recipe + a disciplined model-soup of comparable, complementary own-trained
adapters was the robust top-3.4%-public / 0.85-private result; **every** "smart" augmentation (synthetic,
solver-CoT, external-teacher, self-distillation, spectral surgery) either diluted or overfit and none beat it.
The selection discipline (best + diverse hedge, avoid duplicates) was directly vindicated on the private board.
The remaining path above 0.85 is the **`equation` frontier** (transformation-rule induction) — planned in
`equation-frontier.md` (EQ-0…EQ-4), now being attempted in the late-submission window.

## 7. Housekeeping
- ✅ PR #108 (final-sprint research, kernels, T12, surgery, closeout) merged.
- ⚠ **Rotate the HF read token** embedded in the private `firefly2006/nemo-andy279-prep` Kaggle kernel.
- Equation-frontier (EQ-0…EQ-4) execution tracked in `tasks.md`; this postmortem + the plan ship in PR #113.
