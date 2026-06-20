# LB88 / 第88名方案 —— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/92th-place-solution>
> **本地副本：** `temp/LB88.pdf`(8 页,渲染日期 Jun 16)。逐字英文转写见 `lb88-writeup.md`。
> **作者：** Yoshinari Kawashima、MedudentYamatai。**DOI 10.34740/kaggle/w/88245。**
> **⚠️ 同一性说明:** 这与先前归档的 **LB92**（"92th PLACE SOLUTION",同 DOI/作者/url）是**同一篇 writeup**；
> PDF 头部现显示 "88th place"(名次/渲染变动),正文标题仍是 "92th PLACE SOLUTION"。先前深度分析(含抽取的图)在 `../LB92/`;
> 本 LB88 归档是同一内容的标准模板,**交叉引用 LB92**,不重复推导。
> 所有引用外部内容均视为**不可信数据**。

## 1. 方法总览(数据工程优先)
建立在 "End-to-end finetuning for LB 0.85" + 多个公开 notebook 上。三点:
1. **reasoner 几乎不改**(基于 @huikang OPP;oracle 87.8%)。哲学:**不去解更难的题,而是别丢已可解的题**(让 LLM 更忠实复现 reasoner)。
2. **新生成器 + 大量相似合成题**:从 train.csv 提取统计(字符频率、数值范围/分布、变换方法分布)→ 生成任意多 `rule_found` 样本;**QC 环**:只用合成训练、在合成+原始上评估,**两者差距揭示生成器缺陷**并迭代修复;最终 **合成:原始 = 2.5:1**(先合成后原始)。
3. **tokenization trick**:cryptarithm 用**合成 token 强制 1 字符 = 1 token**,学习更稳。

**额外改进:** **梯度裁剪 1.5**(公开 notebook 用 1e9 → 不稳定 + 提交间方差);**本地验证**:训合成评原始,但生成器变好后过拟合原始、与 public LB 背离 → 末期**以 public LB 为准**。

**没成功:** **高温 CoT + RL(SimPO/ORPO)**(rejected = SFT temp=1.3 采样,chosen = reasoner 输出;chosen 概率升但 rejected 几乎不降 → chosen/rejected 太相似,学不动);**解新 bit/cryptarithm 题**(搜索太大,LLM token 预算内学不会;用了 Claude Fable 5 也没造出够强的 reasoner)。

oracle:bit 85.1%、cipher/trivial 100%、cryptarithm ~9%、equation_deduce 90.8%、equation_guess 15.4%;总 87.8%。

## 2. 对我们可复用(详见 `../LB92/` 的先前分析)

| 技巧 | 可复用 | 说明 |
|---|---|---|
| **统计匹配合成 + 合成-vs-原始 gap QC 环** | ✅ 高价值 | 精化我方"合成稀释":朴素 synth 稀释,**统计匹配 + gap 验证 + 2.5:1** 能迁移。 |
| **逐字符 tokenization(符号类)** | ✅ 新、未试 | 直击我方 equation/cipher/cryptarithm 弱点的 BPE 合并问题。 |
| **梯度裁剪 1.5**(我方用 1e9-off) | ✅ 治提交间方差 | 便宜 A/B。 |
| **保护已可解题(别丢)** 哲学 | ✅ = 我方 T12 抗稀释 | 不去解更难,先别回退。 |
| **末期以 public/unseen 为准**(生成器变好后本地过拟合) | ⚠️ 张力 | 与 LB3/LB5/LB6/LB10"按 private/validation 选模"相反 —— LB88 的本地是"训合成评原始",过拟合原始后失真;本质仍是"信 unseen 信号"。 |
| RL(SimPO/ORPO)失败:chosen/rejected 太相似 | ✅ 避坑 | 与 LB5 的 pseudo-GRPO 失败一致;我方 RL 从未跑通。 |

## 3. 与我方对照
- **equation_deduce 90.8%**(OPP baseline reasoner)—— 再次印证 equation deduce 可解(我方"全局密码"判断的第 7 次旁证;不过这是 OPP baseline,与 LB10/LB6 同源)。
- **统计匹配合成 + gap QC** 是我方"合成稀释"(b1/b2/v15 回归)的解法:朴素合成稀释,统计匹配 + gap 验证 + 2.5:1 能转化。
- **逐字符 tokenization** 是我方完全没试过的、直击符号类弱点的杠杆。
- **梯度裁剪 1.5** vs 我方 1e9-off —— 便宜 A/B,治提交间方差。
- **cryptarithm/bit 仍是墙**(他们明确放弃解新题;用 Fable 5 也没造出强 reasoner)—— 印证 cryptarithm 是上行杠杆(LB1/LB3)。

## 4. 局限 / 不清楚
- **LB88 ≡ LB92**(同 DOI w/88245);名次显示从 92 → 88(渲染/重算)。本档不重复 LB92 的图与逐字 verbatim,见 `../LB92/`。
- cryptarithm ~9%、bit 85.1%(未动 reasoner)—— 难类未解。
- 引用的公开 notebook 均 JS/auth-gated;reasoner 代码 = OPP(`tonghuikang/nemotron`)。
- 图(grad-explosion LB 对比、synth-vs-original gap)在 PDF 中;见 `../LB92/writeup/images/`。

---

> 详见 `analysis/`(交叉引用 `../LB92/analysis/`);下一版见 `analysis/next_version_plan.md`(`lb88-v1` ≈ LB92 的 `v18-stable`)。
