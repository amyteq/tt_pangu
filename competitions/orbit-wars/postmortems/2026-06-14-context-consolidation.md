# Postmortem: context consolidation (orbit-wars, 2026-06-14)

> KCT-001 整理时,从仓库笔记重建 orbit-wars 上下文的快照。完整细节见同目录 `../README.md`(详细日志)。

## Sources read
- `competitions/orbit-wars/README.md`(详细日志:版本史、设计研究、dead-ends)
- `competitions/orbit-wars/EPISODES.md`、`LEAGUE.md`、`VALIDATION.md`
- `competitions/orbit-wars/agent/versions/v4.py`(v4 Scheduler 头注释)
- `worklogs/orbit.md`、`worklogs/orbit2.md`(中文三表 hub)
- GitHub issue #87、PR #92(本任务未联网核实正文)

## Key facts recovered
- Kaggle Orbit Wars(id 138420,$50,000 Featured,~4137 teams,deadline 2026-06-23)。
- 天梯 **1v1**,μ0=600,配对 μ 更新;每天 5 次提交,保留最新 2 个。
- 引擎纯 Python CPU-bound;评测端 torch 实证可用。

## Decisions recovered
- 接受**双轨拆分**(2026-06-10):kuni05(~1137,attributed)为竞争条目 + 自研 Forecast 线。
- 方向 **D1=C**(低成本继续);提交位策略待 deadline 前最后窗口定(D2)。
- 一切改动用 `arena/suite_gate.py` 套件门控,不用自博弈。

## Open blockers
- 硬 cliff:对强档(evogen 1093 / multifocus / kuni05 1240)0-15%;5 个增量杠杆全不过。

## Active tasks recovered
- v4 Scheduler 集合规划对套件门控,争取首个 >0% vs evogen1093;再决定是否换提交位。

## Known submissions/results recovered
- adapted-kuni05 ~1137(↑);Forecast v3 ~686;v2.1 556(退役)。LB 头部 ~1713,top-10 ~1500-1600。
  详见 `submissions.md` / `LEAGUE.md`。

## Bugs recovered
- 见 `bugs.md`(自博弈不预测天梯、mirror 非 50% 基准、终局差分价值、崩溃安全、强档 cliff)。

## Reusable insights
- 离线 gate 必须对齐线上指标;强档靠一体化系统(见 `insights.md`、`_shared/`)。

## Uncertain or missing context
- 私有/最终榜 μ 细节;v4 最新套件门控数值(以 `worklogs/orbit2.md` / issue #87 最新为准)。

## Proposed follow-up issues
- 「orbit-wars: v4 套件门控结果 + 提交位决策(deadline 06-23)」(见 `tasks.md`)。
