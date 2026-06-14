# Notes (中文存档 / zh sidecar)

> 重要中文原始材料的存档与指引。英文规范结论已并入 `strategy.md` / `insights.md` / `bugs.md` / `tracking.md`。
> 原始长文档不改写,仅链接(见 `references.md`)。

## 原始来源(请勿在此改写,链接见 references.md)
- GitHub issue #87 — [Orbit Wars] 长期跟踪与策略讨论(协作机制 + 三表 inline 更新)。
- `worklogs/orbit.md`、`worklogs/orbit2.md` — 中文工作日志镜像(含 📜 工作日志逐日更新)。
- `work/00.orbit.md` — A1(Claude)+ A2(ChatGPT)分析(中文):赛制拆解、模块化架构(ThreatLedger 等)、
  ideas A–I(几何预测核心 / ROI 扩张 / 防守账本 / 同步多源攻击 / 舰队规模分桶 / 彗星策略 / 2p&4p /
  replay mining 模仿 / RL)、提分技巧 1–10(本地 arena > LB、paired-seed A/B、战术事件日志、动作候选剪枝、
  保守发兵、forward simulation 打分、分阶段、发兵求解器、replay 模仿、线上提交管理)。
- `competitions/orbit-wars/README.md`(详细英文日志)、`EPISODES.md`、`LEAGUE.md`、`VALIDATION.md`。

## 关键中文结论摘录(issue #87,逐字)
> 状态快照(2026-06-12):
「LB 头部 ≈ 1713,top-10 ≈ 1500-1600。当前瓶颈(cliff):对弱 agent 胜率 ~100%,对强档(evogen 1093 /
multifocus / kuni05 1240)只有 0-15%。已系统性试完 5 个增量杠杆,全部无法跨越 cliff —— 强档靠的是
一体化协同规划系统,不是可移植的单一机制。方向已定:D1=C(低成本继续)。」

> 方法论结论(可复用):
「自博弈不预测天梯…建了强弱跨度公开 agent 套件后,离线胜率才与天梯对齐…一切改动用套件门控,不用自博弈。
并行竞技场…引擎是纯 Python CPU 负载,GPU 无用。天梯确认为 1v1。强档怎么赢:前向模拟规划器 + 协同多步规划
(开局分支定界 / 多源汇兵同时到达 / 梯度 supply chain / 双方在途台账 / 每回合多波次)。」

## 合规红线(issue #87)
双账号 = 真实注册参赛者(harrysun2006 + firefly2006);同赛二号账号提交默认拒绝,需 `--i-confirm-compliance`
+ issue 留痕 + 人工批准;不打印/提交 credentials。
