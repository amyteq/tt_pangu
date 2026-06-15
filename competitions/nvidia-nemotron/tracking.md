# Tracking — nemo

> English consolidation of GitHub issue **#86** ("Nemotron Model Reasoning Challenge — strategy & tracking hub").
> Original Chinese tables preserved verbatim in [`tracking_zh.md`](./tracking_zh.md). Future status updates
> live here, not in issue #86. `unknown` = not in available evidence.

## Current snapshot (updated 2026-06-15)
- Best **own real-training: 0.86 (3-way model soup** — SVD rank32 of v14(0.4)+c1(0.3)+b1(0.3); compliant own-work, D3), edging the **v14 replay 0.85**. Top **~0.90** (refreshed 2026-06-14), base ~0.47. Deadline **2026-06-15 23:59 UTC**. Quota 5/team/day.
- **T12 hard-val ranking (2026-06-15):** soup 0.764 = v14 0.764 (both ace hard cipher/bit) ≫ base 0.389 ≈ c1 0.389 > v15 0.333 > c2 0.278. The 0.86 soup is **robust, not diluted**; the CoT/synth-augmented adapters (c1/c2/v15) **regress the hardest cipher/bit to at/below base**; `equation` is unsolved by all (≤2/16). See `submissions.md` for the full table.
- Final-sprint B/C runs scored ≤ soup: c1 0.85, b1 0.85, b2 0.84, c2 0.83. The cipher-heavy v11 stage-2 SFTs were **stood down** (a2 corpus 94% cipher → same regression risk T12 shows).
- **Decision: hold the 0.86 soup to close.** Final private-LB selection = **soup (0.86) + v14 (0.85)** (v14 ≫ c1 on hard-val despite equal public LB). Remaining slots left unused.
- Earlier two attempts to beat the then-best 0.85 also regressed: **T7 merge 0.82**, **T11 v15 synth 0.84**.

## Preserved issue tracking tables (translated → English)

### Table 1 — Open Discussions (all confirmed 2026-06-12)
| # | Topic | Decision / confirmation |
|---|---|---|
| D1 | Submit authorization for the B direction (firefly2006) after completion | ✅ Claude may submit directly as firefly2006 |
| D2 | GPU budget for v11 rejection-sampling self-distillation | ✅ approved |
| D3 | Scope of SVD merge (v13) | ✅ merge **only our own** adapters (avoid repack dispute) |
| D4 | Priority of v12 Unsloth route | ✅ confirmed (offline wheels → seq8192 + more steps) |
| D5 | External GPU resource selection | ✅ decided in #83 |
| D6 | Timing of #85 YAML + user-pool work | ✅ **do it post-competition** (scoring first) |
| D7 | Inline issue-update mechanism | ✅ edit comments inline; inplace-update the 3 tables; separate comment only for major results |
| D8 | T10 uses 4 third-party public Kaggle datasets (real fresh training, not repack) | ✅ approved |
| D9 | GPU allocation after A/B | ✅ A→T10 (public 0.87 replay), B→T4 v10; seq8192; keep ≤8h to avoid timeout |

### Table 2 — TODO / directions (T1–T13)
| ID | Direction | Current status | Evidence |
|---|---|---|---|
| T1 | A: nemo-cot-ctx4k (harrysun2006) — masked CoT, seq4096, 580 steps, loss 0.147 | ✅ **LB 0.67** | issue #86 comment 0 |
| T2 | B: nemo-cot-ctx2k (firefly2006) — seq2048, 583 steps, loss 0.186 | ✅ LB 0.42 (negative-sample lesson: right-trunc cut `\boxed{}`) | issue #86 comment 0 |
| T3 | Use daily 5-submission quota | 🟢 ongoing (per-day best banked) | issue #86 |
| T4 | v10: rule-aware CoT data (`firefly2006/nemo-rule4k-v10`) — 8000 ex, 558 steps, loss 0.93, held-out 3/4 | ✅ LB 0.59 (merge-pool member) | issue #86 T4 |
| T5 | v11: rejection-sampling self-distillation (`nemo-v11-sample-a2`/`-b`) | 🟡 stage-1 SAMPLE ran 2026-06-15 (vLLM via aimo-3-utils-0171; a2 → 404 verified CoTs, 94% cipher). Stage-2 SFT (`nemo-v11-sft-d`) **built but stood down** — T12 shows cipher-heavy augmentation regresses hard cats | issue #86 T5 |
| T6 | v12: Unsloth ~1 epoch / seq8192 | 📝 planned (superseded by v14) | issue #86 T6 |
| T7 | multi-adapter SVD merge (`harrysun2006/nemo-merge-t7`) — SVD rank32(1.0·v14+0.25·ctx4k+0.25·v10) | ✅ LB 0.82 (regression; **route closed**) | issue #86 comment 3; PR #94 |
| T8 | time-budget mechanism (v9 timeout fix) | ✅ done (in A/B) | issue #86 T8 |
| T9 | per-comp YAML + user-pool tooling (#85) | 🗓 post-competition (D6) | issue #86 T9 |
| T10 | **v14: public 0.86/0.87 replay recipe** (`harrysun2006/nemo-replay-v14`) — seq8192, 254/254 steps, CCE + MoE 128 tying + lm_head/in_proj/out_proj, loss ~0.05 | ✅ **LB 0.85 (best, +0.18)** | issue #86 comment 2; PR #90 |
| T11 | v15: cryptarithm synth + v14 backbone (`harrysun2006/nemo-synth-v15`) — 2640 ex (cryptarithm 60%), 337/337 steps, loss ~0.002, CoT-answer 1930/1930 | ✅ LB 0.84 (did not exceed v14) | issue #86 comment 4; PR #95 |
| T12 | official metric localization + min-logprob hard-val set (`harrysun2006/nemo-t12-hardval`) | ✅ **done 2026-06-15** — ported official scorer + min-logprob hardest-72 set; ranked adapters: soup/v14 0.764 ≫ base/c1 0.389 > v15 0.333 > c2 0.278. Basis for the hold-0.86 + soup+v14 selection | issue #86 T12 |
| T13 | fix held-out eval truncation (`EVAL_MAX_NEW` 512→7680 + `EVAL_TIME_CAP`=1800s) | ✅ done (in v10) | issue #86 T13 |

## Experiment / idea progress
- **Done & scored:** ctx4k (0.67), ctx2k (0.42), v10 (0.59), v14 (0.85), t7 merge (0.82), v15 synth (0.84), c1 (0.85), c2 (0.83), b1 (0.85), b2 (0.84), **soup (0.86, best)**.
- **Done (eval):** T12 official-metric + min-logprob hard-val ranking — confirmed soup/v14 robust, augmented adapters regress hard cats.
- **Stood down:** v11 stage-2 SFT (T5, cipher-heavy → T12 regression risk); v12 Unsloth (T6, superseded by v14); T9 tooling (post-comp, D6).
- **Closed routes:** T7 weight-space merge (strong+weak dilutes); category-weighted synth (single ≠ total); CoT/synth augmentation degrades the hardest cipher/bit (T12).

## Kernel push status
| Kernel | Account | LB | State |
|---|---|---:|---|
| nemo-cot-ctx4k | harrysun2006 | 0.67 | pushed + evaluated |
| nemo-cot-ctx2k | firefly2006 | 0.42 | pushed + evaluated |
| nemo-rule4k-v10 | firefly2006 | 0.59 | pushed + evaluated |
| nemo-replay-v14 | harrysun2006 | **0.85** | pushed + evaluated (best) |
| nemo-merge-t7 | harrysun2006 | 0.82 | pushed + evaluated |
| nemo-synth-v15 | harrysun2006 | 0.84 | pushed + evaluated |
| nemo-solver-c1 | harrysun2006 | 0.85 | pushed + evaluated (2026-06-15) |
| nemo-solver-c2 | harrysun2006 | 0.83 | pushed + evaluated (2026-06-15) |
| nemo-synth-b1 | firefly2006 | 0.85 | pushed + evaluated (2026-06-15) |
| nemo-synth-b2 | firefly2006 | 0.84 | pushed + evaluated (2026-06-15) |
| nemo-merge-soup | harrysun2006 | **0.86** | pushed + evaluated (2026-06-15, **best**) |
| nemo-v11-sample-a2 / -b | harrysun2006 / firefly2006 | — | data-gen (verified-CoT corpus, vLLM); no submission |
| nemo-t12-hardval | harrysun2006 | — | eval harness (hard-val ranking); no submission |

> ✅ **Refreshed 2026-06-15** via read-only Kaggle API (`kaggle competitions submissions`, both accounts). All listed submissions are `COMPLETE`; private LB not released. See `submissions.md` for the full confirmed table + T12 ranking.
> Reflects evidence current to 2026-06-15.

## Submission / LB status
- Best own-work public LB: **0.86** (`nemo-merge-soup`, 3-way SVD of own adapters). Single-adapter best **0.85** (`nemo-replay-v14`). Leaderboard top **~0.90** (2026-06-14). Private LB `unknown` (not released). Final private-LB selection: **soup (0.86) + v14 (0.85)**. Full confirmed table: `submissions.md`.

## Version map
| LB | Version | Recipe summary |
|---:|---|---|
| 0.47 | identity | untrained adapter (base) |
| 0.61 | v5 | bare-answer SFT |
| 0.44 | v6 | CoT but loss over prompt+padding (bug) |
| 0.65 | v7 | CoT + response-only masking |
| 0.67 | ctx4k (T1) | masked CoT, seq4096 |
| 0.42 | ctx2k (T2) | masked CoT, seq2048 (truncation bug) |
| 0.59 | v10 (T4) | rule-aware CoT (rule + long-CoT mix) |
| **0.85** | **v14 (T10)** | **public replay recipe: CCE + MoE tying + lm_head/Mamba LoRA + seq8192 + huikang corpus + replay-math** |
| 0.82 | t7 | SVD merge v14+ctx4k+v10 → rank32 |
| 0.84 | v15 (T11) | v14 backbone + cryptarithm-weighted synth (~24%) |
| 0.85 | c1 | v14 backbone + 1800 verified real-prompt solver CoT |
| 0.83 | c2 | v14 backbone + 1000 verified CoT (hard-cat emphasis) |
| 0.85 | b1 | v14 backbone + cryptarithm-only synth (~9%) |
| 0.84 | b2 | v14 backbone + cryptarithm+bit synth (~11%) |
| **0.86** | **soup** | **SVD rank32 of v14(0.4)+c1(0.3)+b1(0.3) — own-work 3-way model soup (best)** |

## Evidence links
- GitHub issue #86 (body + comments 0–4) — original hub.
- `tracking_zh.md` — original Chinese tables verbatim.
- `worklogs/nemo.md`, `worklogs/nemo2.md`; `work/00.nemo.md` (analysis); `notes_zh.md` (EN digest).
- PRs #90 (v10+v14), #94 (t7), #95 (v15); kernels under `./kernels/`.
