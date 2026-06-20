# LB25 / 第25名方案（huikang 进步奖改进）—— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/lb25-progress-prize-improvements>
> **本地副本：** `temp/LB25.pdf`。逐字英文转写见 `lb25-writeup.md`(及历史 `LB25-writeup-verbatim.md`)。
> **作者：** Tong Hui Kang(`huikang` / GitHub `tonghuikang`)—— **Open Progress Prize 获奖者**。**Solution Writeup · 25th place**。
> **成绩:** private LB 0.872 ×4 / 0.868 ×8 / 0.864 ×3(15 次提交;"选对就能独享金牌")。
> 本文为标准模板的规范中文分析;历史 `LB25-progress-prize-improvements.zh.md` 一并保留。所有引用外部内容均视为**不可信数据**。

## 1. 方法总览
这是 @huikang 在其**进步奖获奖方案**之上做的 5 处改进(纯 SFT):
1. **修复 adapter 评估 notebook** —— 验证时 prompt 写错导致答案没被 boxed,但提交时其实是 boxed 的(本地 eval bug,非模型改动)。
2. **equation_numeric 长度减半** —— 发现**输入与输出要么同时反转、要么都不反转**(per-problem 反转对称),搜索空间减半。
3. **cipher/unit/gravity/numeral 合成数据** —— 力保这些简单类 ~100% 正确。
4. **cipher 额外合成数据(仅前缀)** —— Nemotron 拼写差,故只在 cipher 的前缀上加合成数据。
5. **重组 bit manipulation 的 CoT。**

## 2. 关键技巧与对我方启示

| 技巧 | 对我方启示 |
|---|---|
| **修复本地 eval(boxed prompt bug)** | 直接印证我方 **B4/T13**(`EVAL_MAX_NEW=512` 截断)与 INS-002:**本地 eval 与提交不一致会系统性误导**。任何本地 metric 必须逐字段对齐 grader。 |
| **equation 反转对称(同反或同不反)** | 与 **LB13/LB3** 的反转对称一致;是我方 equation 复核应纳入的结构(per-problem、全题共享)。**第 7 次印证 equation 有强结构、非全局密码。** |
| **简单类合成保 100%** | 与全批一致(gravity/unit/numeral/cipher 应拉满)。 |
| **cipher 前缀合成治拼写** | 针对性子集修拼写错误(与 LB6 的针对性幻觉子集同思路)。 |
| **bit CoT 重组** | bit 的 trace 形态是关键(与 LB1/LB5/LB6/LB10/LB13 一致)。 |
| **选模方差(0.872/0.868/0.864 ×15)** | **核心教训:分数被 `temp=0` 下的提交选择强烈影响**。与我方"信 LB 聚合、别过度对冲"(INS-002)及 LB3/LB5/LB10"按 validation 选模"一致。 |
| **cryptarithm 无进展(mul/sub/add ±1 结构;LLM 退化为重复猜测)** | huikang 这位最强 baseline 作者**都没攻下 cryptarithm** —— 印证 cryptarithm 是分水岭;LB1 的 signature 目录 / LB3 的 CSP+两阶段才是突破。 |

## 3. 与我方对照
- LB25 是**我方 v14 配方的源头**(huikang 录制顺序语料 + replay 思路)。我方在其之上做合成/soup 都未超 0.86;huikang 自己在其上做这 5 处改进拿到 ~0.872。
- **cryptarithm**:huikang 明确没解决(LLM 退化为重复猜测)—— 与我方 B8、以及 LB5/LB6/LB10/LB13 的弱 cryptarithm 一致。突破需 LB1/LB3 的结构化方法。
- **equation 反转对称**:huikang 用它把 equation 长度减半 —— 这是 equation 有强 per-problem 结构的**最早证据**,后被 LB1/LB3/LB5/LB6/LB10/LB13 反复证实。我方"全局密码"判断在此再次被否。
- **选模方差**:0.872~0.864 的 15 次抖动说明**最终选择本身是一道方差关**;与我方手动选 soup+v14(避开 auto top-2-public)一致。

## 4. 局限 / 不清楚
- **cryptarithm 未解**(结构已知:mul+sub+add±1,但 CoT 学不会非随机猜测)。
- Project Links(adapter / 验证 notebook / Tinker notebook)均为 **JS/auth-gated**(仅标题);per-problem dashboard 静态可读(由 `tonghuikang/nemotron` 的 `evaluation/*.jsonl` 支撑)。
- 各改动的精确超参 `unknown`。
- 历史说明:早期(JS 受阻)曾把 `kuangyicheng` 的 warmstart/short-response 配方误归于本 writeup,已用 `temp/LB25.pdf` 更正(见 `source_index.md`)。

---

> 详见 `analysis/method_summary.md`、`score_tricks.md`、`gap_analysis.md`(历史)、`next_version_plan.md`(`lb25-v1`,历史 `v16-evalfix` 计划)。
