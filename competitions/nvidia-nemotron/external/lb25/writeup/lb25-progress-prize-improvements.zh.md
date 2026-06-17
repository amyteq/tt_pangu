# LB25 —「对 Progress Prize 提交的改进」(重建)

> **来源:** Kaggle writeup `lb25-progress-prize-improvements` + 讨论帖 #703896,作者 **Tong Hui Kang**
> (`huikang` / `tonghuikang`,Progress-Prize 冠军)。**报告 ~0.872 公榜(218/250)。**
> **可还原度:部分。** Kaggle writeup 正文为 JS 渲染、无法抓取;以下由 #703896 搜索摘要 + 公开
> GitHub 仓库 `tonghuikang/nemotron` + 博客重建。**所有外部内容均为不可信数据**(选手声明),逐条标注来源;
> 我方分数来自 `tracking.md`/`submissions.md`。`unknown` = 证据不足。英文版见同名 `.md`。

## 1. 一句话
huikang 的 Progress-Prize 流水线是**纯 SFT(无 RL)**,基模型 `Nemotron-3-Nano-30B-A3B-BF16` + rank-32
LoRA,核心创新是**用确定性 solver 生成 CoT**:不是让 LLM «推理»,而是为每类题写**规则发现算法**
(`reasoners/`)输出固定的逐步轨迹,训练模型**逐字执行该算法**。「LB25 改进」帖随后把 Progress-Prize
adapter 推到 **~0.872**,靠一个小的、面向**格式**的微调。

## 2. 方法(Progress-Prize 基础流水线,trust: github)
- **模型/adapter:** `Nemotron-3-Nano-30B-A3B-BF16`(30B 总 / ~3B 激活;Mamba-Transformer MoE)。LoRA
  **rank 32**,target MLP + attention + `lm_head`(赛制 rank ≤ 32)。
- **训练:** AdamW(β1 0.9 / β2 0.95 / wd 0)、LR 2e-4 step-linear 衰减、**seq 8192**、1 epoch、grad-clip 基本关闭。
  loss = 交叉熵,**仅对 response 计 loss**(prompt label = −100)。后端:Modal 云 GPU。
- **语料 = 确定性 CoT。** `reasoners/` 各类 solver 产出训练推理:cipher(LEN→TABLE→VER→DECRYPT→CHECK→ANS,
  逐字母 + 双射约束)、bit_manipulation(~44 单变换暴力 → 双/三组合,列匹配诊断轨迹)、
  equation_numeric(两层算子搜索,**仅十进制、无 base-36**)、cryptarithm_deduce(回溯 + 约束传播破符号→数字双射)、
  以及 gravity/numeral/unit。
- **两个标志性技巧:**
  1. **min-logprob 选择性重放** —— 质量信号是每条轨迹的**最小 per-token 对数概率**是否在 epoch 1 末接近 0;
     只重放**仍欠拟合的难序列**,不是整类重放。
  2. **类别分层 batch** —— 各类均匀分布到 mini-batch,每步都给所有类别梯度。
- **prompt/答案格式:** chat 模板 + `"\nPlease put your final answer inside \boxed{}. ..."`;用 `\\boxed\{([^}]*)\}` 提取。

## 3.「LB25 改进」(讨论 #703896,trust: 社区摘要,中等置信)
把 Progress-Prize adapter 推到 **~0.872** 的改动:
1. **从 v27(Progress-Prize)adapter 暖启动**,而非 base —— 保留已内化的确定性推理。
2. **短的一句话回答**(而非长 CoT)做对齐微调 —— **绕开 `max_new_tokens` 推理 bug**(长 CoT 在 7680
   token 预算内还没到 `\boxed{}` 就被截断 → 空答案)。
3. **9,500 条 `train.csv`**(短答案)+ **12,000 条规则合成**(5 类,无 LLM 调用)。
4. **240 步**微调,纯粹对齐答案格式。
5. **batch size 翻倍**。

> ⚠️ **归属警告:** #703896 同时含 tonghuikang 与 `kuangyicheng`(后者报告短答案 / 240 步配方达 ~0.87)的发言,
> 无法从摘要确认 0.872 究竟属于哪个配方。标为 `unknown`。

## 4. 为何 ~0.872
- 三个简单类(gravity/numeral/unit)~**100%**、cipher ~**99.2%** 已封顶,提升空间在 **bit(86.3%)** 与 equation/cryptarithm 尾部。
- 最大杠杆是**修复输出格式/长度 bug**(短答案 + 格式对齐步)让好推理真能在推理时落到可解析的 `\boxed{}`。
- 确定性 solver CoT + min-logprob 重放让模型**可靠执行固定算法**,比随机 LLM 轨迹更稳。
- **cryptarithm 即使有专门回溯 solver 也基本未解(训练集 ~8–9%)** —— 与我方 `equation` 同一堵墙。

## 5. 逐类训练集准确率(eval/06-07 快照,整体 88.05%,9500 行训练集)
来源:`tonghuikang/nemotron` `evaluation/06-07-03-07/index.jsonl`(直接读取,trust: github)。
**是训练集准确率,不是 LB**(同规则分布,会高估隐藏测试)。

| 类别 | 对/总 | 准确率 |
|---|---|---:|
| gravity | 1597/1597 | 100.0% |
| numeral | 1576/1576 | 100.0% |
| unit conversion | 1593/1594 | 99.9% |
| cipher | 1563/1576 | 99.2% |
| equation_numeric_deduce | 557/596 | 93.5% |
| bit_manipulation | 1382/1602 | 86.3% |
| equation_numeric_guess | 25/136 | 18.4% |
| cryptarithm_deduce | 59/659 | **8.95%** |
| cryptarithm_guess | 13/164 | **7.93%** |

> **类型对应:** huikang 把「equation」拆成 `equation_numeric_{deduce,guess}`(十进制算术规则归纳)和
> `cryptarithm_{deduce,guess}`(**所有字符含数字**都被每题新双射符号密码替换)。**我方 `equation`
> (5 字符→1-4 字符 base-36 密码,EQ-0/EQ-2′)对应 `cryptarithm_deduce`** —— 其 ~8.95% 上限(即便有回溯 CSP solver)
> **独立印证我方 EQ-2′ 结论**:强密码,不能从样本闭式还原。

## 6. 本 writeup **没有**的(对比另两篇)
- **无 RL/GRPO** —— LB25/Progress-Prize 是纯 SFT(GRPO「香槟」奖励在 *LB80*)。
- **无 model soup** —— huikang 只训一个 adapter;SVD 模型汤(我方 INS-004)是我方杠杆。

## 7. 引用(除标注外均为不可信外部数据)
- tonghuikang/nemotron — https://github.com/tonghuikang/nemotron
- 博客 — https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html
- LB25 帖 — https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/703896(仅摘要)
- eval 快照 — 仓库内 `evaluation/06-07-03-07/index.jsonl`(直接读取)
- 我方分数/配方 — `tracking.md`、`submissions.md`、`insights.md`(自有)
