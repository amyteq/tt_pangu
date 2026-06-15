# Submissions — nemo

> **Refreshed 2026-06-14 via read-only Kaggle API** (`kaggle competitions submissions`, both accounts;
> creds in `.vscode/.env.harry` / `.vscode/.env.may`, read-for-use only). All rows below are confirmed
> `SubmissionStatus.COMPLETE`. Private LB column is empty in the API (not released) → `unknown`.
> Kaggle's submissions API exposes no numeric submission ID; the (date + description) pair is the key.
> Quota: 5/team/day.

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
