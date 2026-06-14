# Submissions — nemo

> ⚠ 多数精确分值分散在 `worklogs/nemo*.md` 与各 kernel 日志;下表为**已知证据**汇总,空缺处标 `?`。
> 早期 LB 进度(identity 0.47 / v5 0.61 / v7 0.65)见 `experiments/kernel/README.md`。

| Date | Version | Run/Experiment | Local CV | Public LB | Private LB | Submit/push type | Artifact | Notes |
|---|---|---|---:|---:|---:|---|---|---|
| 2026-06 | identity | untrained adapter | — | 0.47 | — | kernel | adapter | base 参考 (kernel README) |
| 2026-06 | v5 | bare-answer SFT 120 步 | ? | 0.61 | — | kernel | adapter | kernel README |
| 2026-06 | v7 | CoT + response-only mask 400 步 | ? | 0.65 | — | kernel | adapter | 06-12 前我方最佳 (kernel README / nemo2.md) |
| 2026-06 | v10 | rule-CoT 4k | ? | ? | — | kernel | nemo-rule4k-v10 | PR #90 |
| 2026-06 | v14 | replay recipe | ? | ~0.85 | — | kernel | nemo-replay-v14 | PR #95 描述称 LB 0.85 ⚠ |
| 2026-06-14 | v15 | cryptarithm-weighted synth | ? | running | — | kernel | nemo-synth-v15 | PR #95;生成器 2640 条 |
| 2026-06 | t7 | SVD merge v14+ctx4k+v10 → rank-32 | ? | ? | — | kernel | nemo-merge-t7 | PR #94 |

## Submission checklist
- [ ] local validation passed (validate_kernel.py + fail-fast preflight)
- [ ] submission shape checked (submission.zip @ /kaggle/working)
- [ ] no secrets
- [ ] runtime acceptable (kernel 截止前可跑完)
- [ ] approval obtained (远程提交需人工批准)
- [ ] result recorded (回填本表)
