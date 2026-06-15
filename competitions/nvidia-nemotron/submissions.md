# Submissions — nemo

> **Refreshed 2026-06-15 via read-only Kaggle API** (`kaggle competitions submissions`, both accounts;
> creds in `.vscode/.env.harry` / `.vscode/.env.may`, read-for-use only). All rows below are confirmed
> `SubmissionStatus.COMPLETE`. Private LB column is empty in the API (not released) → `unknown`.
> 2026-06-15 update adds the final-sprint B/C/soup submissions + the T12 hard-val ranking (below).
> Kaggle's submissions API exposes no numeric submission ID; the (date + description) pair is the key.
> Quota: 5/team/day.

## Final-sprint submissions (2026-06-15) — B / C / model-soup

> Confirmed `COMPLETE` via the live Kaggle submissions API on 2026-06-15. The **3-way model
> soup is own work** (SVD merge of our own v14/c1/b1 adapters — compliant, D3 own-adapters-only)
> and is the **new own-training best at 0.86**, edging the v14 replay (0.85).

| Date (UTC) | Account | Version | Public LB | T12 hard-val (72) | Private LB | Status | Description (kernel) |
|---|---|---|---:|---:|---:|---|---|
| 2026-06-15 03:22 | harrysun2006 | **soup** | **0.86** | **0.764** | unknown | COMPLETE | SVD rank32 of v14(0.4)+c1(0.3)+b1(0.3) — 3 complementary 0.85 adapters (replay / verified-solver-CoT / cryptarithm-synth) |
| 2026-06-15 01:12 | harrysun2006 | c1 | 0.85 | 0.389 | unknown | COMPLETE | Solver C1: v14 backbone + 1800 verified real-prompt CoT (cipher/bit/numeral/gravity/unit), seq8192 |
| 2026-06-15 00:52 | harrysun2006 | c2 | 0.83 | 0.278 | unknown | COMPLETE | Solver C2: v14 backbone + 1000 verified CoT (hard-cat: bit/equation/cipher), seq8192 |
| 2026-06-15 01:02 | firefly2006 | b2 | 0.84 | not eval'd | unknown | COMPLETE | Synth B2: v14 backbone + cryptarithm+bit synth ~1000 (~11%), seq8192 |
| 2026-06-15 00:52 | firefly2006 | b1 | 0.85 | not eval'd | unknown | COMPLETE | Synth B1: v14 backbone + cryptarithm-only synth ~800 (~9%), seq8192 |

### T12 hard-val ranking (official-metric, min-logprob hardest 72; `harrysun2006/nemo-t12-hardval` v2, 2026-06-15)
Greedy decode (official `max_tokens=7680, temp=0`), `\boxed{}`/last-number extractor, exact-or-1e-2 match.
Hard-val = min-logprob hardest-N-per-category (16 each bit/equation/cipher, 8 each numeral/gravity/unit).

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

### Final private-LB selection (lock before 23:59 UTC)
Select the **two** submissions that count for private scoring:
1. **soup — 0.86** (`2026-06-15 03:22`): best public + robust on hard-val.
2. **v14 — 0.85** (`2026-06-12 23:36`): equal public LB to c1 but **much stronger on hard-val (0.764 vs c1 0.389)** → safer second pick than c1/b1/v15. (soup + v14 are correlated — soup is 40% v14 — but the v14 family is the demonstrably robust one, so the concentration is intentional.)

## Real-training campaign (own work — 2026-06-09 → 2026-06-14)

| Date (UTC) | Account | Version | Public LB | Private LB | Status | Description (kernel) |
|---|---|---|---:|---:|---|---|
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
- **Best own real-training submission: 0.86** (the 3-way model **soup**, 2026-06-15 — SVD merge of our
  own v14/c1/b1 adapters; compliant own-work, D3). Edges the v14 replay (0.85). T12 confirms it is
  robust on hard problems (hard-val 0.764, tied with v14), not a lucky public-LB artifact.
- **Previous own-training best: 0.85** (`nemo-replay-v14`, 2026-06-12) — still the strongest *single*
  adapter and the recommended second private-LB selection.
- **Raw account public max: 0.86** — also matched by a **2026-05-15 public-fork** submission
  (`[LB][SCORE][0.86]`), not our own training. The 0.86 soup above reaches the same number via
  compliant own-work, so the account's public max and own-work best now coincide at 0.86.
- Current leaderboard top: **~0.90** (refreshed 2026-06-14; was ~0.89 in the issue snapshot).

## Submission checklist
- [ ] local validation passed (validate_kernel.py + fail-fast preflight)
- [ ] submission shape checked (submission.zip @ /kaggle/working; rank32/α32)
- [ ] no secrets
- [ ] runtime acceptable (≤8h wall-clock guard)
- [ ] approval obtained (remote submit needs human approval)
- [ ] result recorded (this table)
