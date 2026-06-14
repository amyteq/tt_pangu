# NVIDIA Nemotron Model Reasoning Challenge (nemo)

> 别名:nemo / nemotron。Kaggle slug:`nvidia-nemotron-model-reasoning-challenge`。

## Status snapshot
- status: **active**(deadline **2026-06-15 23:59 UTC**,迫近)
- phase: submission(冲分中)
- current objective: 提升 **cryptarithm** 瓶颈类正确率(论坛共识 0.86→0.89 的杠杆)
- best known local/CV: 各 kernel 自带 held-out eval(见 submissions.md);⚠ 无统一 CV 汇总
- best known LB/public: **~0.85(v14 replay)**;base ~0.47,榜首 ~0.89;v15 提交结果待回收
- current blocker: cryptarithm 类偏弱;截止前提交额度有限(5 次/天/队)
- next task: 回收 v15(cryptarithm-weighted synth)线上分;截止前用满额度

## Key links
- rules: ./rules.md
- strategy: ./strategy.md
- tasks: ./tasks.md
- submissions: ./submissions.md
- bugs: ./bugs.md
- references: ./references.md
- insights: ./insights.md
- experiments: ./experiments/(kernels v10/v14/v15、t7 svd-merge、synth 生成器)
- postmortem: ./postmortems/2026-06-14-context-consolidation.md

## Current top 3 priorities
1. v15(cryptarithm 加权合成 CoT)线上分回收;若超过 v14 则在截止前提交。
2. 截止前(06-15)用满双账号(harrysun2006 / firefly2006)每日提交额度,优先覆盖最佳候选。
3. 守住已验证的 v14 replay 配方,避免回归(见 bugs.md 的运行期坑)。

## Latest update
- date: 2026-06-14
- source: PR #95(v15 synth)、worklogs/nemo2.md
- summary: 在 v14 replay 主干上掺入「cryptarithm 加权确定性合成 CoT」(生成器 in-kernel,2640 条,
  CoT-answer 一致性 1930/1930),目标抬升 cryptarithm 瓶颈;kernel `nemo-synth-v15` 已 push(running)。
