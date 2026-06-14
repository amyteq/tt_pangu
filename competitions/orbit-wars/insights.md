# Insights — Orbit Wars

## Competition-specific insights
- **官方 `garrison+1` 基线对移动/产兵目标是错的**:中立静态、敌方按 `production*travel_ticks` 增长,需领产兵。
  Evidence: `./README.md`(exact capture rule,引擎行号)。
- **终局(k=H)差分净舰值才守恒正确**:对所有 k 计会惩罚在途舰。Evidence: `./README.md`(Forecast key bug)。

## Potentially reusable insights

### INS-001: 离线 gate 必须对齐线上指标(否则零预测力)
- type: rule
- confidence: high
- evidence: `./README.md`(self-play 不预测天梯;suite_gate 才对齐)
- transfer scope: 任何有线上天梯 / 隐藏评测的竞赛
- status: validated(本竞赛内)
- notes: 已登记 `_shared/skill-candidates.md`(ladder-predictive-gate)+ `_shared/insights.md`。

### INS-002: 强对手靠一体化系统取胜,单一机制不可移植
- type: anti-pattern
- confidence: medium
- evidence: `./README.md`(5 个 bolt-on 杠杆全不过 cliff)
- transfer scope: agent / 复杂规划类竞赛
- status: candidate
- notes: 推论是「整体重构 > 增量移植」;待更多竞赛验证泛化性。
