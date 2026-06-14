# Postmortem: context consolidation (nemo, 2026-06-14)

> KCT-001 整理时,从仓库笔记重建 nemo 上下文的快照。只记录有证据的内容,缺口显式标注。

## Sources read
- `competitions/nvidia-nemotron/experiments/kernel/README.md`(配方、坑、score 进度)
- `worklogs/nemo.md`、`worklogs/nemo2.md`(中文策略 hub;2026-06-12 快照 + D1–D7)
- 各 `kernels/*/kernel-metadata.json`、`experiments/synth/nemo_synth_gen.py`、`experiments/merge/svd_merge.py`
- PR #90 / #94 / #95(合并说明)

## Key facts recovered
- 赛制:提交 **rank≤32 LoRA adapter**(基模 Nemotron-3-Nano-30B-A3B,Mamba+MoE);评测端 greedy
  `max_tokens=7680, temp=0`;提取 `\boxed{}` 比对(精确或数值 1e-2);指标 **accuracy**;9 类推理题;
  train ~9500 行;测试集隐藏;每队 **5 次/天**;**deadline 2026-06-15 23:59 UTC**。
- LB 进度:base ~0.47 → v5 0.61 → v7 0.65(06-12 前最佳)→ v14 replay **~0.85**(PR #95 描述);榜首 ~0.89。
- 双账号:harrysun2006 / firefly2006(B 方向并行)。

## Decisions recovered
- D1 B 方向提交授权 ✅;D2 v11 自蒸馏 GPU 预算 ✅;D3 SVD merge 仅限**自训** adapter ✅;
  D4 Unsloth 路线优先级 ✅;D5 外部 GPU 选型(#83)✅;D6 #85 YAML/user-pool **赛后再做** ✅;
  D7 inline 更新机制 ✅。(详见 `worklogs/nemo2.md` 表1)

## Open blockers
- cryptarithm 类正确率偏低(瓶颈,论坛 0.86→0.89 杠杆)。
- deadline 迫近(06-15);每日提交额度有限。

## Active tasks recovered
- v15(cryptarithm-weighted synth)线上分回收;截止前用满双账号额度;t7 SVD merge 对照(可选)。

## Known submissions/results recovered
- 见 `submissions.md`(identity 0.47 / v5 0.61 / v7 0.65 有证据;v10/v14/v15/t7 部分 LB 待回填)。

## Bugs recovered
- 见 `bugs.md`(ptxas-blackwell、数据 glob、BatchEncoding `.shape`、prompt+padding loss、F821/`.shape` 预检、cryptarithm 弱)。

## Reusable insights
- response-only masking 是 CoT SFT 关键;CoT 中间值预计算;push 前 lint + 单样本预检(见 `insights.md`、`_shared/`)。

## Uncertain or missing context
- v14 / v15 / t7 的确切公开/私有 LB(v14 ~0.85 来自 PR 描述;v15 running)。
- 精确 train 行数;nemo 追踪 issue 号(本任务未联网核实)。

## Proposed follow-up issues
- 「nemo 截止后归档」:回填 submissions.md 全部 CV/LB,补 final postmortem。
