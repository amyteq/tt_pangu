# LB25 —「对 Progress Prize 提交的改进」(直接据 writeup)

> **来源:** Kaggle writeup `LB25-progress-prize-improvements`,作者 **Tong Hui Kang**(`huikang`/`tonghuikang`,
> Progress-Prize 冠军),**直接读自 `temp/LB25.pdf`**(页面渲染)。**可还原度:完整**(已拿到正文 —— 取代此前
> JS-blocked 重建;那版误把 `kuangyicheng` 的「暖启动 / 短答案 / 240 步」配方当成了本文,实际本文**没有**那些)。
> 外部内容=不可信数据;我方分数见 `tracking.md`。作者给的数据浏览器:
> `https://nemotron.huikang.dev/evaluation.html?logpath=06-07-03-07&problem=021ed764`。

## 1. 一句话
本文列出 huikang 把 Progress-Prize 提交往私榜推的**具体改动**。仍是**纯 SFT**(基础流水线 = 确定性 solver CoT,
见 §4)。四项改动是**针对性修复**,其中最关键的是一个**本地评测 bug 修复**,而非模型改动。

## 2. 四项改动(据 writeup 原文)
1. **修复 adapter 评测。**「我发现 prompt 错了,导致答案**在验证里没有被 box**,但其实**提交时是 box 的**」。
   → 他的*本地验证 harness* 用了错的 prompt,低估了准确率;模型在真实提交 prompt 下没问题。是**验证/指标 bug**,
   经所链接的评测 notebook 修复。
2. **把 `equation_numeric` 长度减半。**「我发现要么输入**和**输出都被反转,要么都不反转」—— 一个联合反转对称性,
   所以一半情况冗余,训练数据可减半。
3. **对 `cipher`、`unit conversion`、`gravity`、`numeral` 用合成数据训练** ——「希望在这些题上保证 100% 正确」
   (把简单/结构化类别锁在上限)。
4. **重新组织 `bit manipulation` 的思维链(CoT)。**

## 3. 结果 + 选择教训(据原文)
- **私榜:「15 次提交里,0.872 出现 4 次,0.868 出现 8 次,0.864 出现 3 次」** —— 即很紧的分布;**0.872 只被 15 次中的 4 次命中。**
- 「**如果选中『对的』那次提交本可拿单人金牌,但很多队都能这么说**」。→ **选择方差**教训:在顶部,锁定哪两次
  与配方同样重要(呼应我方 INS-005/INS-007:选最好 + 一个多样化对冲;surgery ×1.15 私榜 −0.02)。

## 4. Cryptarithm ——「我**没**取得进展」(对我方最关键的技术内容)
huikang 的 `cryptarithm` ≈ **我方 `equation` base-36 密码**。原文:
- 「**我没能在 cryptarithm 上取得进展。**」
- 「我在截止前 3 天发现,**很多题里有一个乘法、一个减法、一个加法(但每个都可能再 +1 或 −1)**。」
- 「我试着让 CoT 猜得比随机好,但训练后的 LLM **退化成重复猜测**。」

> **→ 可执行的 EQ-2′ 新线索。** 这是对我们(EQ-2′)没破解的密码的*独立结构假设*:隐藏操作可能是在秘密符号→值
> 映射 σ 下的 **三项复合 `≈ A·B − C + D`、每项 ±1**。我方 EQ-2′ 测过*单*操作(`in mod M`、`floor(in/D)`、
> `A±B`、`A÷B`、`A·B`、`K·in mod M`)和单一位置切分 —— **从未测过乘法+加法的复合 + ±1 余量**。值得周六后做
> 一次定向约束求解。⚠ 警告:huikang **也没破解**,且我方 EQ-0 发现我们的 prompt 是单一 5 字符→1-4 字符串
> (操作数结构不明显)—— 当作线索而非答案。再次印证 `equation`/`cryptarithm` 对所有人都是**有界的墙**。

## 5. 基础流水线(背景 —— `github.com/tonghuikang/nemotron`,trust: github)
与 Progress-Prize 提交一致:基座 `Nemotron-3-Nano-30B-A3B-BF16`、LoRA **rank 32**(MLP+attn+lm_head)、seq 8192、
仅 response 计 loss 的 CE;逐类**确定性 solver CoT**(`reasoners/`)让模型逐字执行;**min-logprob** 作为每条轨迹的
训练/质量信号(数据浏览器「Training」页可见);类别分层 batch。(此背景在此前重建里是对的;LB25 的*改动*是 §2。)

## 6. 逐类训练集准确率(据所链接数据浏览器 / 仓库 `evaluation/06-07-03-07`,整体 88.05%)
**训练集准确率,非 LB**(同规则分布 → 高估隐藏测试)。同此前:

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

> 四项改动对应此表:#3(合成)针对已近 100% 的简单类做**锁定**;#2(equation_numeric)针对 93.5%/18.4% 的数值行;
> #4(bit CoT)针对 86.3% 的 bit 缺口;cryptarithm(8–9%)是没动的墙(§4)。

## 7. 项目链接(据 writeup 页面)
- **nemotron-adapter-private** —— Kaggle Model(Public,Usability 0.7,~13 天前)—— 提交用 adapter。
- **[private] Adapter validation …** —— Kaggle Notebook(Public,3 赞,~2 月前)—— 评测 notebook(修复 #1 的对象)。
- **[private] Tinker submission …** —— Kaggle Notebook(1 赞,~13 天前)。
(均 Kaggle 托管;正文 JS 锁 —— 仅标题/元数据。)

## 8. 引用
- **writeup(全文):`temp/LB25.pdf`**(Kaggle writeup 渲染;§2–§4、§7 的一手来源)。
- 数据浏览器 — https://nemotron.huikang.dev/evaluation.html?logpath=06-07-03-07&problem=021ed764(作者)。
- 仓库/博客 — https://github.com/tonghuikang/nemotron · https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html。
- 我方分数/配方 + EQ-2′ — `tracking.md`、`submissions.md`、`equation-frontier.md §8`、`insights.md`(自有)。
