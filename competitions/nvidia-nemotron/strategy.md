# Strategy — nemo

## Current direction
在已验证的 **v14 replay 配方(LB ~0.85)** 主干上,定点提升 **cryptarithm** 瓶颈类:掺入确定性合成
CoT(v15),并用 **SVD merge**(t7:v14 + ctx4k + v10 → rank-32)在额度内组合多条已训 adapter。
双账号(harrysun2006 / firefly2006)并行扩大每日提交覆盖。

## Open discussions
> 详细讨论与历史决策(D1–D7 已确认)见 `worklogs/nemo2.md` 的三表;此处仅留当前活跃问题。

### D001: 截止前(06-15)提交额度分配
- status: open
- context: 每队 5 次/天 × 双账号;v15 running,t7 merge 可选。
- options: (a) 全押 v15;(b) v15 + t7-merge 对照;(c) 守 v14 不动。
- current leaning: 优先提交「明显超过 v14」的候选(KCA 自主提交策略 Scenario 1/2)。
- evidence: `worklogs/nemo2.md`;CLAUDE.md KCA autonomous submission strategy。
- follow-up: v15 分数回收后定。

## Hypotheses
- **H1**:cryptarithm 加权合成 CoT(每步预计算、无内联算术、finality 行)能抬升该类正确率而不伤其它类。
  证据来源:v10「shallow-reasoning regression」教训 → v15 设计(PR #95)。
- **H2**:仅 merge **自训** adapter(不掺公开 adapter)可在额度内取增益且避免 repack 争议(D3 已确认)。

## Rejected ideas
- v6:CoT 但 loss 覆盖 prompt+padding(bug)→ 0.44,已废(改 response-only masking,见 kernel README)。
- 掺入公开 adapter 做 merge:范围收敛为「仅自训 adapter」(D3)。
