# References — nemo

## Kaggle
- NVIDIA Nemotron Model Reasoning Challenge — slug `nvidia-nemotron-model-reasoning-challenge` — 主竞赛 — 高相关。
- 基模型 `metric/nemotron-3-nano-30b-a3b-bf16`(Nemotron-3-Nano-30B-A3B,Mamba+MoE) — 提交 adapter 的基座 — 高相关。

## Discussions
- 论坛共识:cryptarithm 是 0.86→0.89 的杠杆 — 见 `worklogs/nemo2.md` — 高相关。

## Notebooks
- `experiments/kernel/nemotron-lora-baseline.py` — LoRA SFT baseline(percent-format 源) — 高相关。
- `experiments/kernels/{nemo-rule4k-v10,nemo-replay-v14,nemo-synth-v15,nemo-merge-t7}/` — 各版本 kernel — 高相关。

## Papers / repos
- 训练语料 dataset:`dgxchen/nemotron-cot-tong`(CoT traces,已注明出处);`mayukh18/nemotron-packages`(离线 wheels);`mohamedamr992/replay-math`(replay)。

## Internal notes
- `experiments/kernel/README.md` — 配方、坑、score 进度 — 高相关。
- `experiments/synth/nemo_synth_gen.py` — 合成 CoT 生成器(v15) — 高相关。
- `experiments/merge/svd_merge.py` — SVD adapter merge(t7) — 中相关。

## Worklogs
- `worklogs/nemo.md`、`worklogs/nemo2.md` — 策略 hub(中文三表)+ 历史决策 D1–D7 — 高相关。

## Issues / PRs
- PR #90(v10 rule-CoT + v14 replay kernels)、PR #94(T7 SVD merge)、PR #95(v15 synth)。
- nemo 策略追踪 issue(中文 hub) — 见 `worklogs/nemo2.md` 内嵌内容。⚠ issue 号未在本任务内核实。
