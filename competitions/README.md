# Competitions Dashboard

> 真实 Kaggle 竞赛工作区总览。详情在各竞赛目录;本页保持简短。

## Active competitions

| Competition | Status | Type | Phase | Best CV/local | Best LB/public | Last submit/push | Current blocker | Next task |
|---|---|---|---|---:|---:|---|---|---|
| [nvidia-nemotron](nvidia-nemotron/) (nemo) | active | llm | submission | per-kernel held-out | **0.85** (v14 replay) | v15 push 0.84 (2026-06-14); best=v14 0.85 | 0.85 是当前杠杆天花板(T7 merge 0.82 / v15 0.84 均回归);deadline **06-15** 迫近 | 守住 0.85 收官(可选 half-dose cryptarithm synth) |
| [orbit-wars](orbit-wars/) (orbit) | active | simulation_agent | iteration | suite ~54.8% | own **686** (v3 peak) / attributed **1151** (kuni05) | harry latest-2: kuni05 **1085.4** + v3.2 **660.0** (2026-06-14) | 强档 cliff（0-15% vs evogen/multifocus/kuni05） | v4 Scheduler 下一刀（反击窗/集群重锤）；末 3 天冻结 best-2 |

> LB 说明:nemo 最好 **0.85**(`nemo-replay-v14`,issue #86 comment 2 确认);两次冲 0.85+ 均回归(T7 merge 0.82、v15 synth 0.84)。orbit（Kaggle API 2026-06-14 确认):attributed adapted-kuni05 当前 **1085.4**(峰值 1151）、自研 v3.2 **660.0**;榜首 ~1746。详见 [`nvidia-nemotron/tracking.md`](nvidia-nemotron/tracking.md) · [`orbit-wars/tracking.md`](orbit-wars/tracking.md)。
> Kaggle 只读刷新（2026-06-14）：nemo own 最好 **0.85**(v14);账号原始公开最大 **0.86**(2026-05-15 public-fork,非自训);榜首 **~0.90**;private LB 未发布。详见 [`nvidia-nemotron/submissions.md`](nvidia-nemotron/submissions.md)。

## Recently updated
- **2026-06-14** nvidia-nemotron — context consolidation into English canonical docs + `tracking.md` + `_zh` sidecars (KCT-002); v15 synth = 0.84, best held at v14 0.85.
- **2026-06-14** orbit-wars — v4 Scheduler(PR #92);文档集补全(KCT-001)。
- **2026-06-14** orbit-wars — context consolidation into English canonical docs + `tracking.md` + `_zh` sidecars (KCT-003); ladder refreshed read-only: kuni05 1085.4 / v3.2 660.0, top ~1746.

## Cross-competition notes
- 见 [`_shared/insights.md`](_shared/insights.md):离线 gate 必须对齐线上指标;push 前 lint + 单样本预检。
- 见 [`_shared/common-bugs.md`](_shared/common-bugs.md):CV/LB 背离、kernel runtime 不一致、依赖/离线 wheels、追踪 issue 膨胀。

## Other competition material (not active)
- **tpu-getting-started**(Petals to the Metal,M10):真实竞赛,但仍留在 `experiments/tpu-getting-started/`——
  迁移会破坏 `scripts/`、`tests/`、`.claude/skills/`、`docs/` 中**禁止修改**的承重引用。详见
  [`_shared/migration-notes.md`](_shared/migration-notes.md)(已登记为待后续 PR 迁移)。

## Links
- _shared insights: [`_shared/`](_shared/)
- templates: [`_templates/`](_templates/)
- migration notes: [`_shared/migration-notes.md`](_shared/migration-notes.md)
