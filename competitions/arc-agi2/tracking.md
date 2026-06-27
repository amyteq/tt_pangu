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
