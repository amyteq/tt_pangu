# Strategy — Orbit Wars

> 完整版本史、设计研究与 dead-ends 见 `./README.md`(详细日志)。此处只留当前方向与活跃讨论。

## Current direction
**接受双轨拆分**(closeout 2026-06-10,方向 D1=C「低成本继续」):
- **竞争性条目**:`adapted-kuni05`(公开 LB-1240.5 agent,**已注明出处**)~1137,仍向 ~1240 爬升。
- **自研线**:`Forecast v3.1`(从零;bit-exact 前向模拟 + 差分终局净舰值 + 防守)~686;v4「Scheduler」
  在其上做集合规划 beam search(`agent/versions/v4.py`,issue #87 / PR #92)。
- 用「强弱跨度公开 agent 套件」(`arena/suite_gate.py`)门控,**不**用自博弈(自博弈不预测天梯)。

## Open discussions
> 完整 D 表见 `worklogs/orbit2.md` / issue #87;此处留当前活跃项。

### D001: 提交位策略(latest-2 tracked)
- status: open
- context: 当前 latest-2 = [Forecast v3 ~686, kuni05 ~1137];再提交任何版本都会挤掉其一。
- options: 保持现状 / 最后 24-48h 用一个位换自研最强版。
- current leaning: 保持 kuni05;deadline(06-23)前最后窗口视 v4(C 线)成果再定。
- evidence: `worklogs/orbit2.md`(D2);`./README.md`(submission trade-off)。
- follow-up: v4 套件门控结果。

## Hypotheses
- **H1**:强档靠**一体化协同规划系统**取胜(开局序列搜索 + 多源汇兵 + supply chain + 多波次 + 前向模拟),
  单一机制不可移植 → v4 走「集合规划」整体重构而非继续 bolt-on。证据:`./README.md`「design study」。

## Rejected ideas
> 五个增量杠杆均**试过→否决**(套件门控,均不过 cliff),详见 `./README.md`:
- consolidation ✗、safe_drain ✗(v3a)、defense(仅自博弈有效)、multi-source ✗、opening-planner ✗。
