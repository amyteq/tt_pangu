# Insights — nemo

## Competition-specific insights
- **response-only loss masking 是 CoT SFT 的关键**:覆盖 prompt+padding 直接掉到 0.44;改 response-only
  后 0.65(v7)。Evidence: `experiments/kernel/README.md`。
- **CoT 里每个中间值要预计算、不要内联算术**:v10 的 shallow-reasoning regression 教训直接塑造了 v15
  合成数据设计。Evidence: PR #95 描述。

## Potentially reusable insights

### INS-001: push 前静态 lint + 单样本 fail-fast 预检
- type: rule
- confidence: high
- evidence: `experiments/kernel/README.md`(F821 + 预检各省 ~2h GPU)
- transfer scope: 任何 GPU kernel / 长跑训练竞赛
- status: candidate
- notes: 已登记到 `_shared/skill-candidates.md`(kernel-prepush-validate)。

### INS-002: 定点提升瓶颈类(category-weighted 合成数据)
- type: tactic
- confidence: medium
- evidence: PR #95(cryptarithm 加权 synth)
- transfer scope: 分类别评测的推理 / NLP 竞赛
- status: candidate
- notes: 线上效果待 v15 回收确认。
