# 跨竞赛洞见 (cross-competition insights)

> 只总结**仓库笔记有证据**支持的内容;不臆造。每条附 evidence 链接。

## Confirmed cross-competition insights
- **离线 gate 必须对齐线上指标,否则零预测力。** orbit-wars 自博弈离线赢 91% 却在天梯几乎同分;
  改用「强弱跨度的公开 agent 套件」门控后才与天梯对齐。nemo 同理强调 held-out eval + fail-fast
  preflight。Evidence: `competitions/orbit-wars/README.md`(self-play 不预测天梯一节)、
  `competitions/nvidia-nemotron/experiments/kernel/README.md`(held-out eval / preflight)。
- **推送前静态校验省下 ~2h GPU。** nemo 用 `ruff` F821 + fail-fast 单样本预检拦截 NameError/`.shape`
  等运行期错误。Evidence: `competitions/nvidia-nemotron/experiments/kernel/README.md`。

## Candidate insights
- **「从强对手反推架构,而非移植单一机制」**:orbit-wars 五个增量杠杆全部不过 cliff,强档靠一体化系统取胜。
  是否可泛化为通用策略仍待更多竞赛验证。Evidence: `competitions/orbit-wars/README.md`(incremental path exhausted)。

## Rejected / competition-specific only
- orbit-wars 的 `kaggle_environments` 引擎机制(确定性轨道、捕获规则)是该竞赛特有,不可迁移。

## Evidence links
- `competitions/orbit-wars/README.md`
- `competitions/nvidia-nemotron/experiments/kernel/README.md`
- `worklogs/orbit.md`, `worklogs/orbit2.md`, `worklogs/nemo.md`, `worklogs/nemo2.md`
