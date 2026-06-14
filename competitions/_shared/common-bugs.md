# 反复出现的失败模式 (common bugs)

> 跨竞赛复现的坑;每条尽量附 evidence。

- **submission shape errors** — 提交文件形状 / 列 / 顺序不符。⚠ 通用风险,待按竞赛补证据。
- **CV/LB mismatch** — 本地分与线上分背离。Evidence: orbit-wars 自博弈 vs 天梯严重背离
  (`competitions/orbit-wars/README.md`);通用教训:gate 必须对齐线上指标。
- **notebook runtime mismatch** — kernel 运行期与本地不一致。Evidence: nemo `.shape` /
  `BatchEncoding`、ptxas-blackwell 只读挂载不可执行
  (`competitions/nvidia-nemotron/experiments/kernel/README.md`)。
- **dependency / Kaggle kernel mismatch** — 离线 wheels / docker image / 包版本不匹配。
  Evidence: nemo 离线 wheels(`mayukh18/nemotron-packages`)、Triton/ptxas 路径
  (同上 kernel README)。
- **long tracking issue token bloat** — 追踪 issue 正文膨胀。Evidence: nemo/orbit 均采用
  「三表 inplace 更新 + 重大结果才发独立 comment」来控噪(`worklogs/nemo2.md`、`worklogs/orbit2.md`)。
- **stale docs or duplicate experiment folders** — 文档过期 / 实验目录重复。本次迁移即为整理动作
  (见 `migration-notes.md`)。
