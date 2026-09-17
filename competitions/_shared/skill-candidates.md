# Skill candidates(停车场)

> 仅登记未来可能提炼成 KCA skill 的候选。**不**新增 / 修改 `.kca/skills/`。
>
> A candidate leaves this file by being **scheduled into a `kg-*` skill**, not by being built as a skill of its own — most candidates are a section of an existing stage, not a stage. When one lands, keep its row, set `status: landed`, and name where it went, so the evidence stays attached to the behaviour it justified.

## Candidate: kernel-prepush-validate
- status: **landed** (issue #192) — folded into `kg-submit` § *Pre-push validation*, backed by `docs/tooling/kaggle-kernel-ops.md` §5.
- source competitions: nvidia-nemotron
- problem: kernel 运行期错误(F821 / `.shape` / ptxas 路径)曾各耗 ~2h GPU。
- evidence: `competitions/nvidia-nemotron/kernels/validate_kernel.py`(静态 lint + fail-fast preflight)。原先登记的 `experiments/kernel/README.md` 不存在,#192 更正为实际文件。
- proposed future asset: 通用「push 前静态 lint + 单样本预检」skill。

## Candidate: ladder-predictive-gate
- status: **landed** (issue #192) — folded into `kg-audit` § *Does the offline gate predict the leaderboard?*
- source competitions: orbit-wars
- problem: 自博弈 / 朴素离线 gate 对线上无预测力,需「强弱跨度对手套件」才能对齐天梯。
- evidence: `competitions/orbit-wars/README.md`(suite_gate.py;self-play 不预测天梯)
- proposed future asset: 通用「构建并用对齐线上的离线评测套件」skill。
