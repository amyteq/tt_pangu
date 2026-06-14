# Tasks — nemo

## Now
- 回收 `nemo-synth-v15`(cryptarithm-weighted synth)线上分。

## Next
- 若 v15 > v14:截止前(06-15)在双账号额度内提交最佳候选。
- t7 `nemo-merge-t7`(SVD merge:v14+ctx4k+v10 → rank-32)对照提交(可选)。

## Backlog
- 统一各 kernel 的 held-out CV 汇总到 submissions.md(目前分散在各 kernel 日志)。

## Blocked
- 无硬阻塞;受 deadline(06-15)与每日额度约束。

## Done
- v5/v7 baseline、v10 rule-CoT、v14 replay(~0.85)、t7 svd-merge 脚手架、v15 synth 生成器(2640 条,
  CoT-answer 一致性 1930/1930)。证据:PR #90 / #94 / #95。

## Proposed GitHub issues
> 本任务不创建 issue;仅列建议。
- 标题:「nemo: 截止后归档 — 汇总各 kernel held-out CV 与最终 LB」
  验收:submissions.md 填全 v10/v14/v15/t7 的 CV + 公开/私有 LB;写 postmortem。
