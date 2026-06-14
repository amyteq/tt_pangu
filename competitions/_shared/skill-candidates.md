# Skill candidates(停车场 — 本任务不实现)

> 仅登记未来可能提炼成 KCA skill 的候选。**不**新增 / 修改 `.kca/skills/`。

## Candidate: kernel-prepush-validate
- status: candidate
- source competitions: nvidia-nemotron
- problem: kernel 运行期错误(F821 / `.shape` / ptxas 路径)曾各耗 ~2h GPU。
- evidence: `competitions/nvidia-nemotron/experiments/kernel/README.md`(validate_kernel.py + fail-fast preflight)
- proposed future asset: 通用「push 前静态 lint + 单样本预检」skill。
- not implemented in this task.

## Candidate: ladder-predictive-gate
- status: candidate
- source competitions: orbit-wars
- problem: 自博弈 / 朴素离线 gate 对线上无预测力,需「强弱跨度对手套件」才能对齐天梯。
- evidence: `competitions/orbit-wars/README.md`(suite_gate.py;self-play 不预测天梯)
- proposed future asset: 通用「构建并用对齐线上的离线评测套件」skill。
- not implemented in this task.
