# Rules — NVIDIA Nemotron Model Reasoning Challenge

> 仅记录有证据事实;不确定项标注「⚠ 待确认」。证据:`worklogs/nemo2.md`(2026-06-12 快照 + 赛制一句话)、
> `experiments/kernel/README.md`。

## Problem
9 类推理题(reasoning),需对隐藏测试集输出可被提取比对的答案。

## Data
- train 9500 行(`worklogs/nemo2.md` 称 ~9500;kernel README 早期称变体语料)。⚠ 精确行数以官方为准。
- 真实测试集**隐藏**。

## Metric
- **accuracy**:从模型输出中提取 `\boxed{}` 答案,与标准答案**精确匹配或数值误差 ≤ 1e-2**。

## Submission format
- 提交 **rank ≤ 32 的 LoRA adapter**,基模型 **Nemotron-3-Nano-30B-A3B**(Mamba + MoE)。
- kernel 产出 `submission.zip` 至 `/kaggle/working`;经 Kaggle storage 提交。

## Constraints
- 评测端:**greedy 解码**,`max_tokens=7680`,`temp=0`。
- 提交额度:**每队 5 次/天**。
- internet off;GPU kernel(`NvidiaRtxPro6000`,见 `kernel-metadata.json`)。

## Deadline / schedule
- **2026-06-15 23:59 UTC**(`worklogs/nemo2.md` 快照)。⚠ 临近,以官网为准。

## External data / kernel / internet / GPU rules
- 训练语料用到外部 Kaggle dataset(已注明出处):`dgxchen/nemotron-cot-tong`、
  `mayukh18/nemotron-packages`(离线 wheels)、`huikang/...`、`mohamedamr992/replay-math` 等
  (见各 `kernel-metadata.json` 的 `dataset_sources`)。internet off,依赖走离线 wheels。

## Unclear rules (⚠ 待确认)
- 精确 train 行数(9500 vs 变体语料)。
- v14 / v15 的确切公开 LB(v14 ~0.85 来自 PR #95 描述;v15 running)。
