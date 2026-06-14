# Competitions Dashboard

> 真实 Kaggle 竞赛工作区总览。详情在各竞赛目录;本页保持简短。

## Active competitions

| Competition | Status | Type | Phase | Best CV/local | Best LB/public | Last submit/push | Current blocker | Next task |
|---|---|---|---|---:|---:|---|---|---|
| [nvidia-nemotron](nvidia-nemotron/) (nemo) | active | llm | submission | per-kernel held-out | **~0.85** (v14) ⚠ | v15 kernel push (2026-06-14) | cryptarithm 类瓶颈;deadline **06-15** 迫近 | 回收 v15 线上分,截止前用满额度 |
| [orbit-wars](orbit-wars/) (orbit) | active | simulation_agent | iteration | suite ~54.8% | **~1137** (adapted-kuni05) | latest-2: [Forecast v3 ~686, kuni05 ~1137] | 强档 cliff(0-15% vs evogen/kuni05) | v4 Scheduler 套件门控,争取 >0% vs evogen1093 |

> LB 说明:nemo `~0.85` 来自 PR #95 描述(v14 replay),v15 running ⚠;orbit `~1137` 为已注明出处的 adapted-kuni05(竞争条目),自研 Forecast 线 ~686。

## Recently updated
- **2026-06-14** nvidia-nemotron — v15 cryptarithm-weighted synth kernel(PR #95)。
- **2026-06-14** orbit-wars — v4 Scheduler(PR #92);文档集补全(KCT-001)。

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
