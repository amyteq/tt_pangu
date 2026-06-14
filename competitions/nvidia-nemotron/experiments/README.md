# nvidia-nemotron — experiments

> 由 `experiments/nvidia-nemotron-model-reasoning-challenge/` 迁入(KCT-001,`git mv` 保留历史)。
> 重产物(adapter 权重、训练日志)走 `runs/` / object storage,不进 git。

## Layout
- `kernel/` — LoRA SFT baseline(`nemotron-lora-baseline.py` 为源;`validate_kernel.py` 预推送校验)。
- `kernels/`
  - `nemo-rule4k-v10/` — rule-CoT,seq4k(v10)。
  - `nemo-replay-v14/` — replay recipe(v14,LB ~0.85)。
  - `nemo-synth-v15/` — cryptarithm-weighted 合成 CoT(v15)。
  - `nemo-merge-t7/` — SVD merge(v14+ctx4k+v10 → rank-32)。
- `merge/svd_merge.py` — SVD adapter merge 工具(t7)。
- `synth/nemo_synth_gen.py` — in-kernel 合成 CoT 生成器(v15)。

## Workflow
- `.py`(percent-format)为源,`kca nb to-ipynb` 生成 `.ipynb`(gitignored 构建产物)。
- 推送前跑 `validate_kernel.py`(no-GPU,F821 + masking 校验)。
- 详见 `kernel/README.md`。
