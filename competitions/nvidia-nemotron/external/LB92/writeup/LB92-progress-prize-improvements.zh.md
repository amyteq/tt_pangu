# LB92 —「92th PLACE SOLUTION」(直接据 writeup)

> **来源:** Kaggle writeup,作者为**团队 —— Yoshinari Kawashima(`yoshinarikawashima`)+ MedudentYamatai
> (`taikiyamamura`)**,**直接读自 `temp/LB92.pdf`**(整页渲染;2026-06-16;DOI `10.34740/kaggle/w/88245`)。
> **可还原度:完整** —— 取代此前仅生态重建(当时作者/分数/方法均未知,现已确认)。外部内容=不可信数据(选手声明),
> 逐条标注;我方分数见 `tracking.md`。英文版见同名 `.md`。

## 0. 一句话
一个**数据工程优先**的干净方案,明确**不**去解难类 —— 目标是**忠实复现公开 reasoner 的 87.8% 解题率**,并用**更多、
统计匹配的合成数据** + 两个稳定性技巧来缩小到 LB 的差距。建立在公开 notebook(「End-to-end finetuning for LB 0.85」、
「Training with Unsloth to Achieve 0.85 LB」、「Tinker submission notebook」);**reasoner 是 Tong Hui Kang 的**
(Open Progress Prize),**几乎没改**(与 LB25/LB80 同源)。

## 1. 三大支柱
**(1) 几乎不改 reasoner(CoT 生成逻辑)。** 确定性 reasoner 解出 train 的 **87.8%**(8341/9500),但最好的公开 notebook
只有 **0.86**。论点:*模型没能复现 reasoner 已经解出的题* → **目标=别丢已可解的题,而非解更难的。** 逐类 reasoner 准确率
(其表;= huikang):

| 类别 | 解出/总 | 准确率 |
|---|---|---:|
| cipher | 1576/1576 | 100.0% |
| gravity | 1597/1597 | 100.0% |
| numeral | 1576/1576 | 100.0% |
| unit_conversion | 1594/1594 | 100.0% |
| equation_numeric_deduce | 541/596 | 90.8% |
| bit_manipulation | 1364/1602 | 85.1% |
| equation_numeric_guess | 21/136 | 15.4% |
| cryptarithm_deduce | 59/659 | **9.0%** |
| cryptarithm_guess | 13/164 | **7.9%** |
| **合计** | **8341/9500** | **87.8%** |

**(2) 新生成器 + 统计匹配的合成数据(标志性杠杆)。** 假设:reasoner-vs-LB 的差距是**训练数据不足**。他们做了一个生成器,
用**从 `train.csv` 提取的任务级统计**(字符频率、数值范围/分布、变换方法分布)生成任意数量 `rule_found` 样本。
**质量控制环:** **只在合成上训练**,在**合成 + 原始**上评测;若合成完美模仿原始,两个评测准确率应相等 —— **差距揭示生成器缺失的因素**,
迭代修复(分析 → 生成 → 训练 → 评测两者 → 比差距 → 修 → 重复)。**最终提交:合成 : 原始 = 2.5 : 1**(先合成后原始)。更长训练改善了 loss,尤其难任务。

**(3) 两个稳定性技巧:**
- **cryptarithm 的逐字符 tokenization。** BPE 有时把多个符号合成一个 token(如 `}!` → token 119020)。他们用**强制每个字符编码为单个
  token 的合成 token** → 符号类学习更稳定。*(对我方 equation/cipher 直接相关的新杠杆 —— 我们没做过。)*
- **梯度裁剪 = 1.5**(公开 notebook 用 **1e9 = 基本关闭**)。1e9 导致**训练不稳定**与**提交间分数方差**(某次 grad-norm 在
  **step 107 飙到 25,089**);裁到 1.5 稳定下来。*(与我方 v14 / mspawar「grad-clip 关」相反 —— 一个治本的方差修复。)*

## 2. 验证策略(又是「别信本地」主题)
赛程中段前用**合成训练、原始评测**。但生成器变好后模型**过拟合原始**,**本地验证与公榜背离** → 最终阶段**以公榜(未见数据)为准**,
不再信本地。*(呼应 LB25 的 eval bug 与我方 T12「以 LB 聚合为准」—— 本地代理会漂移。)*

## 3. 没奏效的
- **SimPO / ORPO 的 RL。** 造 *rejected* 时用 SFT 模型在 **temp 1.3** 采样;*chosen* = reasoner 输出。偏好学习**没提升**准确率,弃用。
  日志里 *chosen* 概率升、但 *rejected* 概率**几乎没降**(奖励图:`chosen` 平 ~0、`rejected` 噪声负)。诊断:**chosen 与 rejected 太相似** → 学习信号不足。
  *(又一个独立的「RL 在此打不过 SFT」结果 —— 对应 mspawar 的二值失败 / DPO 有限。)*
- **解新难题。** bit_manipulation & cryptarithm 那种 LLM 能*模仿*的 CoT 很难:解法需**大量搜索**,在 token 预算内 LLM 学不来。
  甚至用了 **Claude Fable 5** 也没能造出足够强的 reasoner。*(印证发现/token 预算之墙 —— 同 LB80「发现泄漏」+ 8192 token 限制。)*

## 4. 对我方的意义
- **逐字符 tokenization** 是对我方符号类(equation/cipher)的**新、未试杠杆** —— 便宜可测。
- **grad-clip 1.5** 可能削减我方提交方差(我们用 1e9 关闭,正是他们修掉的公开设置)。
- **统计匹配合成 + 差距闭合验证环** 精化了我方「合成稀释」结论:我方 synth(b1/b2/v15)回归,而他们的*有帮助*,因为**匹配了 train.csv 统计**、
  用 **2.5:1 比例 + 合成-vs-原始差距质控**、且训练更久。朴素 synth 稀释;**统计匹配、差距验证过的 synth 可以有用。**
- **RL(SimPO/ORPO)对他们也失败** —— 印证 LB80 的二值失败诊断与我方对 RL 的保守。
- 他们和所有人一样**没破 cryptarithm/equation**(有界的墙),并明确选择保护简单类。

## 5. 引用
- **writeup(全文):`temp/LB92.pdf`**(Kaggle writeup 渲染;DOI 10.34740/kaggle/w/88245;一手来源)。
- 所建立的公开 notebook(Kaggle,JS 锁):「End-to-end finetuning for LB 0.85」、「Training with Unsloth to Achieve 0.85 LB」、
  「Tinker submission notebook」;reasoner = Open Progress Prize(huikang)。
- 我方分数/配方 + EQ-0/EQ-2′ — `tracking.md`、`submissions.md`、`equation-frontier.md §8`、`insights.md`(自有)。
