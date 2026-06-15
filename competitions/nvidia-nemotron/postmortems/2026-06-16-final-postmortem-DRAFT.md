# Final postmortem — NVIDIA Nemotron Model Reasoning Challenge (DRAFT, private LB pending)

> **Status: DRAFT scaffold.** Public LB is final; the **private LB has not been released** yet.
> Sections marked `⟨FILL@private⟩` are to be completed once the private leaderboard is out.
> Competition closed **2026-06-15 23:59 UTC**. Own-work best public **0.86**; top of LB **~0.90**.
> Sources: `submissions.md`, `tracking.md`, `insights.md`, `bugs.md`, the 2026-06-14/06-15 postmortems.

## 1. Headline (public)
- **Best own-work public LB: 0.86** — the 3-way SVD **model-soup** `v14(0.4)+c1(0.3)+b1(0.3)` (compliant own training, no repack).
- Progression: base 0.47 → v5 0.61 → v7 0.65 → ctx4k 0.67 → **v14 replay 0.85** → **soup 0.86**.
- The clean public-recipe replay (CCE + MoE-expert tying + lm_head/Mamba LoRA + seq8192 + huikang corpus + replay-math) was the single biggest lever (0.67→0.85); a model-soup of comparable+complementary 0.85 adapters added the last +0.01 (0.86).

## 2. Final private-LB selections (locked before close)
Two separate account entries (registered teammates; each selects its own 2):
| Account | Pick 1 | Pick 2 | Rationale |
|---|---|---|---|
| harrysun2006 | **soup — 0.86** | **v14 — 0.85** | best + most-diverse robust hedge (v14 tied with soup on hard-val 0.764). Deliberately NOT the surgery 0.86 (a soup ×1.15 duplicate → no hedge), NOT andy279/v11 (regressed). |
| firefly2006 | **b1 — 0.85** | **b2 — 0.84** | may's two best own submissions (cryptarithm-synth on the v14 backbone). |

`⟨FILL@private⟩` — confirm the selections as recorded on the Kaggle UI at close.

## 3. Full public-LB results (own work)
| version | account | public LB | private LB | recipe |
|---|---|---:|---:|---|
| **soup** | harry | **0.86** | `⟨FILL@private⟩` | SVD rank32 of v14+c1+b1 (0.4/0.3/0.3) — best |
| surgery scale_1.15 | harry | 0.86 | `⟨FILL@private⟩` | soup ×1.15 LoRA (spectral surgery; neutral/duplicate) |
| v14 | harry | 0.85 | `⟨FILL@private⟩` | public replay recipe |
| c1 | harry | 0.85 | `⟨FILL@private⟩` | v14 + 1800 verified solver CoT |
| b1 | may | 0.85 | `⟨FILL@private⟩` | v14 + cryptarithm-only synth (~9%) |
| v15 | harry | 0.84 | `⟨FILL@private⟩` | v14 + cryptarithm-weighted synth (~24%) |
| b2 | may | 0.84 | `⟨FILL@private⟩` | v14 + cryptarithm+bit synth (~11%) |
| c2 | harry | 0.83 | `⟨FILL@private⟩` | v14 + hard-cat verified CoT |
| t7 merge | harry | 0.82 | — | SVD v14+ctx4k+v10 (strong+weak → dilution) |
| andy279 | may | 0.81 | `⟨FILL@private⟩` | v14 + 1700 external-teacher solver-CoT — regressed |
| v11 self-distill | may | 0.80 | `⟨FILL@private⟩` | v14 + 261 rejection-sampled CoT — regressed |
| ctx4k / v7 / v5 / v10 / v6 / ctx2k / identity | both | 0.67 / 0.65 / 0.61 / 0.59 / 0.44 / 0.42 / 0.47 | — | early SFT line |

## 4. The full arc + what worked / didn't
- **Worked:** faithful public-replay reproduction (biggest lever); model-soup of comparable+complementary adapters (0.85→0.86).
- **Neutral:** spectral/SVD adapter surgery (0.86, tied — can't add missing capability).
- **Regressed / didn't beat 0.86:** rule-CoT v10 (0.59), strong+weak SVD merge t7 (0.82), cryptarithm synth v15/b1/b2 (0.84–0.85), hard-cat solver c2 (0.83), **external-teacher solver-CoT andy279 (0.81)**, **v11 self-distillation (0.80)**.
- **Cross-cutting lesson (held all the way):** *augmentation dilutes the clean replay recipe; single-category gains ≠ total* (B8). It survived our strongest final-sprint attempts (high-quality DeepSeek/GPT-5.4 teacher CoT included).
- **Unsolved frontier:** the `equation` category (≤2/16 on hard-val for every adapter) — no direction cracked it.

## 5. Reusable insights (validated this competition)
- INS-001 push-time static lint + single-example fail-fast preflight (saved repeated ~2h GPU losses).
- INS-002 eval harness must mirror the official metric (decode length + extractor) — but **note**: even a min-logprob hard-val (T12) was a *noisy* LB predictor here (surgery +1/78 → 0.00 public delta). Treat small local-eval gaps as noise.
- INS-003 weight-space merge only helps among comparable+complementary adapters (t7 strong+weak regressed; soup comparable+complementary gained).
- INS-004 model-soup of comparable+complementary members beats each member (0.85→0.86).
- INS-005 (new) post-hoc spectral surgery reweights existing directions → can't add missing capability; only helps a *mis-calibrated* adapter, ~neutral on a well-calibrated soup.
- INS-006 (new) external-teacher solver-CoT, even high-quality, dilutes a strong replay backbone at meaningful dose (single-cat ≠ total again).
- Offline vLLM on the Blackwell image: aimo-3-utils-0171 (py3.12/cu128/vllm0.17.1), `--target` install + PYTHONPATH + invalidate_caches (see `reference_vllm_offline_kaggle_blackwell`).

## 6. `⟨FILL@private⟩` — to complete when the private LB releases
- Private scores for each selected submission (soup, v14, b1, b2) + the non-selected ones (for the public→private overfitting analysis).
- **Public→private delta**: did 0.86 hold, or did it shake out? Did v14 (hedge) ever beat the soup on private? Did the surgery 0.86 (had we picked it) differ from soup?
- **Final rank / percentile** for each account.
- **Verdict on the selection**: was soup+v14 the right hedge vs soup+surgery? Did the augmented adapters (b1/b2/andy279) hold or drop more on private?
- One-paragraph final lesson + any insight promotions to `_shared/`.

## 7. Housekeeping
- Rotate the HF read token embedded in the private `firefly2006/nemo-andy279-prep` Kaggle kernel.
- Merge PR #108 (final-sprint research, kernels, T12 ranking, surgery + closeout) after review.
- Move this DRAFT → `2026-06-16-final-postmortem.md` once `⟨FILL@private⟩` sections are completed.
