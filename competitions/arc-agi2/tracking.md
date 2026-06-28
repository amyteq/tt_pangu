# Tracking — ARC-AGI-2

> Experiment + submission log. Empty until we run something. One row per experiment; keep it paper-grade
> (the Grand Prize is writeup-scored). Discipline (CLAUDE.md): hypothesis → change → seed → local pass@2 →
> runtime/cost → artifact path → interpretation → submit? decision.

## Submissions (LB)
| Date | Kernel/version | Local pass@2 | Public LB | Private LB | Notes |
|---|---|---:|---:|---:|---|
| — | (none yet) | — | — | — | env/harness built; no kernel pushed yet |

## Live public LB (read-only API refresh 2026-06-26)
| Rank | Team | Public LB |
|---:|---|---:|
| 1 | nvbanana | **50.56** |
| 2 | Junhua Yang | 35.14 |
| 3 | Fan of Tong Hui Kang | 34.44 |
| 4 | Koushik Rudra | 33.89 |
| 5 | Sanjay Dutt / Van-Phuc Huynh | 33.47 |
> 967 teams; deadline 2026-11-02; **our account (harrysun2006) is entered** (`userHasEntered=True`).
> #1 nvbanana (50.56) is a large outlier vs the ~33–35 pack — note the **2x jump over 2025's 24%** floor.

## Experiments
| Date | ID | Hypothesis | Change | Seed | Local pass@2 | Runtime/cost | Decision |
|---|---|---|---|---|---:|---|---|
| 2026-06-26 | harness-oracle | metric is correct | submission == solutions | — | **100.0%** | <1s | ✅ scorer validated |
| 2026-06-26 | baseline-identity | trivial floor | out=in (both attempts) | — | 0.0% | <1s | expected; ARC-2 has no identity tasks |
| 2026-06-26 | baseline-mcto | constant-output floor | modal train output + input | — | 0.0% | <1s | expected floor |
| 2026-06-26 | baseline-shape0 | canvas-shape floor | zeros@modal-shape + input | — | 0.0% | <1s | expected floor |
| 2026-06-27 | ttt-core-oracle | AIRV scaffolding is correctly wired | full augment→infer→deaug→PoE/vote pipeline w/ perfect-augmented-decode oracle | 0 | **100.0%** | ~2s | ✅ pipeline validated end-to-end (167/167) |
| 2026-06-27 | ttt-core-dummy | pipeline doesn't inflate | same pipeline, decode=echo augmented input | 0 | 0.0% | ~2s | ✅ no false positives |
| 2026-06-28 | ttt-rung1-sample10 | rung-1 (0.5B+TTT, no pretrain) scores on real eval | Qwen2.5-0.5B-Instruct, per-task LoRA TTT 64 steps, 8-aug AIRV, on snorlax 4090 | 0 | **0.0%** (0/10) | ~15min/10 tasks (11–182s/task) | model emits well-formed grids but wrong; **0% = missing offline pretrain** (no ARC prior). GPU layer itself validated. |
| 2026-06-28 | rung1-pretrain | offline pretrain on 1000 train tasks (the ARC prior) | Qwen2.5-0.5B LoRA r32, 12.1k aug examples, 1 epoch | 0 | train loss 0.69→0.29 | 861s (14min) on 4090 | adapter learns the grid format/mappings on train distribution |
| 2026-06-28 | ttt-rung1-pretrained-sample20 | does the pretrain lift eval score? | pretrained adapter + per-task TTT 64 + 8-aug AIRV | 0 | **0.0%** (0/20) | ~25min | **rung-1 ceiling ≈ 0% on ARC-2 eval.** Decode probe: structured grids but WRONG dims (14×6 vs 18×8) + wrong content; rotated view degenerates. Capacity limit, not a bug (oracle=100%). Matches lit: 8B→16.5%, NVARC 4B+synth+TRM→24%. |

## Baselines / reference points (external, for orientation)
| Source | Score | Constraint context |
|---|---:|---|
| NVARC (2025 Kaggle winner, ARC-AGI-2) | 24.03% private | in-Kaggle: 12h / no-internet / ~$0.20/task |
| ARChitects (2025, #2) | 16.53% | in-Kaggle |
| MindsAI (2025, #3) | 12.64% | in-Kaggle |
| Human individual avg | 66% | public eval |
| Human panel | 100% | ≥2 solvers, <2 attempts each |
| o3-medium | ~3% | (vs ~53% on ARC-AGI-1) |

## Decision log
- 2026-06-26 — folder created from research scan; status = research/prep. No compute committed.
- 2026-06-26 — T0/T1 executed: live LB confirmed (top **50.56**, 967 teams, account entered); public data
  downloaded (1000 train + 120 eval, gitignored); submission schema confirmed from `sample_submission.json`
  (`{task_id: [{attempt_1, attempt_2}]}`); **local pass@2 harness built + validated** (oracle 100%, baselines
  0%, 8/8 unit tests). Next: read 2025 tech report (T0.3), scope a TTT baseline (T2).
- 2026-06-27 — declined a request to push 4 kernels: our only candidates were 0% baselines + no kernel
  infra existed; chose (with human) to **build a real TTT baseline first**.
- 2026-06-27 — T0.3 done (recipe in `ttt-recipe.md`); **T2.1a done** — model-agnostic TTT core in `solver/`
  (augment/serialize/ttt_data/select/run) built + validated (oracle 100%, dummy 0%, 31/31 tests, ruff clean).
  **T2.1b (GPU/model layer) is blocked on the compute decision (T0.4).** Still no Kaggle push/submit.
- 2026-06-28 — **T2.1b GPU layer built + run on snorlax 4090** (rung-1: Qwen2.5-0.5B + per-task LoRA TTT,
  `solver/model.py` + `run_eval.py`). Fixed OOM (bs1 + grad-checkpoint + seq filter) and a parser bug
  (ragged-row normalization). End-to-end works; **10-task sample = 0/10 (0%)**.
- 2026-06-28 — **T2.1c offline pretrain done** (`solver/pretrain.py`): 0.5B LoRA on 1000 train tasks
  (12.1k aug examples, loss 0.69→0.29, 14min). **Eval WITH the pretrained adapter still = 0/20 (0%).**
  Decode probe shows structured-but-wrong grids (wrong dims/content). **Conclusion: rung-1 (0.5B) ceiling
  on ARC-AGI-2 eval is ~0% — a model-capacity limit, not a bug** (oracle harness = 100%). Consistent with
  2025 results (8B ARChitects 16.5%, NVARC 4B+synth+TRM 24%). **Recommend escalating to rung-2** (4–8B +
  RE-ARC pretrain + DFS/PoE) for any non-trivial score, or pivoting to the Grand-Prize/writeup angle.
  No Kaggle push/submit. snorlax powered down to save cost pending the rung decision.
