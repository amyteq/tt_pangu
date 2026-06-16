# Submissions — nemo

> **PRIVATE LB RELEASED 2026-06-16.** Both team accounts finished **0.85 private**. harrysun2006 (`flyingfox`)
> public rank **150/4350** (0.86); private top 0.92. Public→private was robust (no shake-up). Key: **soup
> 0.86→0.85** (most robust 0.86, selected); **surgery 0.86→0.84** (−0.02, worst-aging — *not* selected, vindicated);
> **b2 0.84→0.85** (+0.01, the may hedge that paid off). Full analysis + per-submission private deltas:
> [`postmortems/2026-06-16-final-postmortem.md`](./postmortems/2026-06-16-final-postmortem.md).
>
> **Refreshed 2026-06-15 via read-only Kaggle API** (`kaggle competitions submissions`, both accounts;
> creds in `.vscode/.env.harry` / `.vscode/.env.may`, read-for-use only). All rows below are confirmed
> `SubmissionStatus.COMPLETE`. Private LB column is empty in the API (not released) → `unknown`.
> 2026-06-15 update adds the final-sprint B/C/soup submissions + the T12 hard-val ranking (below).
> Kaggle's submissions API exposes no numeric submission ID; the (date + description) pair is the key.
> Quota: 5/team/day.

## T12 hard-val ranking (official-metric, min-logprob hardest 72; `harrysun2006/nemo-t12-hardval` v2, 2026-06-15)
Greedy decode (official `max_tokens=7680, temp=0`), `\boxed{}`/last-number extractor, exact-or-1e-2 match.
Hard-val = min-logprob hardest-N-per-category (16 each bit/equation/cipher, 8 each numeral/gravity/unit).
The final-sprint submissions themselves are listed in the campaign table below.

| adapter | hard-val acc | bit | equation | cipher | numeral/gravity/unit |
|---|---:|---|---|---|---|
| **soup** | **0.764** | 13/16 | 2/16 | 16/16 | 8/8 each |
| **v14** | **0.764** | 14/16 | 2/16 | 15/16 | 8/8 each |
| base (no adapter) | 0.389 | 0/16 | 0/16 | 8/16 | 8 / 7 / 5 |
| c1 | 0.389 | 1/16 | 0/16 | 3/16 | 8/8 each |
| v15 | 0.333 | 0/16 | 0/16 | 0/16 | 8/8 each |
| c2 | 0.278 | 1/16 | 0/16 | 2/16 | 7 / 3 / 7 |

**Findings:**
- **The 0.86 soup is robust, not diluted** — tied with v14 (0.764) and best overall; both ace hard cipher/bit.
- **Augmented adapters (c1/c2/v15) sit at/below the base model on the hardest cipher/bit** (c1 cipher 3/16 < base 8/16) despite being trained on cipher/bit CoT. The base anchor rules out a load artifact: they change behaviour (easy cats → 24/24) but *degrade* the hardest categories. Confirms "augmentation dilutes the clean replay recipe", amplified on the hard slice.
- **`equation` is unsolved by everyone (≤2/16)** — the only real frontier; cipher-heavy data does not touch it.
- **Decision (2026-06-15):** hold the 0.86 soup; stand down the cipher-heavy v11 stage-2 SFTs (a2 corpus was 94% cipher → same regression risk). Remaining daily slots left unused.

### Final-sprint extra submissions (2026-06-15, all scored)
| submission | account | public LB | note |
|---|---|---:|---|
| surgery `scale_1.15` | harrysun2006 | 0.86 | spectral surgery on the soup (×1.15 LoRA); **tied/duplicate** of soup → no hedge value |
| andy279 frontier | firefly2006 | **0.81** | v14 recipe + 1700 external-teacher solver-CoT (eq/bit) → **regressed** (dilution) |
| v11 self-distill | firefly2006 | **0.80** | v14 recipe + 261 rejection-sampled CoT → **regressed** |

None beat the 0.86 soup; the augmentation-dilutes / single-cat≠total lesson held even against external-teacher CoT.

### Final private-LB selection (lock before 23:59 UTC)
Select the **two** submissions that count for private scoring:
1. **soup — 0.86** (`2026-06-15 03:22`): best public + robust on hard-val.
2. **v14 — 0.85** (`2026-06-12 23:36`): equal public LB to c1 but **much stronger on hard-val (0.764 vs c1 0.389)** → safer second pick. **Pick v14, NOT the surgery 0.86** (a near-duplicate of soup = no hedge) and NOT andy279/v11 (regressed). Manually select to avoid the auto "2-highest-public" = soup+surgery no-hedge trap.

## Real-training campaign (own work — 2026-06-09 → 2026-06-15)

| Date (UTC) | Account | Version | Public LB | Private LB | Status | Description (kernel) |
|---|---|---|---:|---:|---|---|
| 2026-06-15 ~12 | harrysun2006 | **soup** | **0.86** | unknown | COMPLETE | **SVD model-soup of v14+c1+b1 (0.4/0.3/0.3) → rank-32 — new best, own real-training** |
| 2026-06-15 01:12 | harrysun2006 | c1 | 0.85 | unknown | COMPLETE | v14 backbone + verified real-prompt solver-CoT (balanced ~1800) |
| 2026-06-15 00:52 | harrysun2006 | c2 | 0.83 | unknown | COMPLETE | v14 backbone + verified solver-CoT (hard-cat emphasis ~1000) |
| 2026-06-15 01:02 | firefly2006 | b2 | 0.84 | unknown | COMPLETE | v14 backbone + cryptarithm+bit synth (~11%) |
| 2026-06-15 00:52 | firefly2006 | b1 | 0.85 | unknown | COMPLETE | v14 backbone + cryptarithm-only synth (~9%) |
| 2026-06-14 05:53 | harrysun2006 | v15 (T11) | 0.84 | unknown | COMPLETE | v14 backbone + 2640 cryptarithm-weighted synth (60% crypt), seq8192, 337/337 steps |
| 2026-06-13 23:54 | harrysun2006 | t7 merge | 0.82 | unknown | COMPLETE | SVD merge v14@1.0 + ctx4k@0.25 + v10@0.25, per-module rank-32 |
| 2026-06-12 23:36 | harrysun2006 | **v14 (T10)** | **0.85** | unknown | COMPLETE | replay recipe: huikang corpus (7830) + replay-math (2.0M ans tok), seq8192, 254/254 steps, CCE + MoE tying + lm_head/in_proj/out_proj |
| 2026-06-12 09:53 | firefly2006 | v10 (T4) | 0.59 | unknown | COMPLETE | rule-CoT: 4000 rule traces (6 cat) + 4000 long CoT, seq4096, 558 steps |
| 2026-06-11 22:40 | firefly2006 | ctx2k (T2) | 0.42 | unknown | COMPLETE | response-masked LoRA, seq2048, 583 steps (eval 0/8 = truncation artifact) |
| 2026-06-11 22:39 | harrysun2006 | ctx4k (T1) | 0.67 | unknown | COMPLETE | response-masked LoRA, seq4096, 580 steps |
| 2026-06-10 09:31 | harrysun2006 | v7 | 0.65 | unknown | COMPLETE | response-masked LoRA, 400 steps, LR 2e-4 cosine |
| 2026-06-10 04:00 | harrysun2006 | v6 | 0.44 | unknown | COMPLETE | CoT 120 steps (loss over prompt+padding bug) |
| 2026-06-10 04:00 | harrysun2006 | v6′ | 0.47 | unknown | COMPLETE | CoT SFT 120 steps, submitted from Kaggle storage |
| 2026-06-10 02:27 | harrysun2006 | v5 | 0.61 | unknown | COMPLETE | bare-answer SFT, 120 steps (loss 1.48); ptxas fix validated |
| 2026-06-09 23:45 | harrysun2006 | identity | 0.47 | unknown | COMPLETE | untrained identity adapter (pipeline validation) |

## Earlier public-fork exploration (2026-05-15 — pre real-training; NOT our own training)

| Date (UTC) | Account | Public LB | Private LB | Status | Description |
|---|---|---:|---:|---|---|
| 2026-05-15 00:44 | harrysun2006 | 0.50 | unknown | COMPLETE | "NVIDIA Nemotron Submission Demo" notebook v1 |
| 2026-05-15 00:34 | harrysun2006 | 0.85 | unknown | COMPLETE | "THK public fork 2026-05-14 (v14 tinker-adapter)" — public fork |
| 2026-05-15 00:18 | harrysun2006 | **0.86** | unknown | COMPLETE | "[LB] [SCORE] [0.86]" — public fork |

## Best score — honest reading
- **Best own real-training submission: 0.86** (`nemo-merge-soup`, 2026-06-15) — an SVD **model-soup** of
  three own-trained, comparable+complementary 0.85 adapters (v14 replay + c1 verified-solver-CoT + b1
  cryptarithm-synth, weights 0.4/0.3/0.3, rank-32). Real training, no repack (D3-compliant). This broke the
  0.85 ceiling (+0.01).
- Earlier own-work best was 0.85 (`nemo-replay-v14`). The final-sprint individual runs tied or trailed it
  (b1 0.85, c1 0.85, b2 0.84, c2 0.83); only the **soup** exceeded it.
- **T12 hard-val (2026-06-15) confirms the soup is robust**, not a public-LB fluke: 0.764 on the hardest 72,
  tied with v14 and best of all candidates; the augmented adapters (c1/c2/v15) regress to at/below base
  there. → Final private-LB selection: **soup (0.86) + v14 (0.85)** (v14 is the strongest single adapter
  and far ahead of c1 on hard-val).
- Note: a 2026-05-15 **public-fork** submission also showed 0.86, but that was a repack (not own training);
  the soup now gives a **compliant own-work 0.86**.
- Current leaderboard top: **~0.90** (refreshed 2026-06-15).

## Submission checklist
- [ ] local validation passed (validate_kernel.py + fail-fast preflight)
- [ ] submission shape checked (submission.zip @ /kaggle/working; rank32/α32)
- [ ] no secrets
- [ ] runtime acceptable (≤8h wall-clock guard)
- [ ] approval obtained (remote submit needs human approval)
- [ ] result recorded (this table)
