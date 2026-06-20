# LB109 / 第109名方案 —— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/heuristics-for-bit-cypher-and-equations>
> **本地副本：** `temp/LB109.pdf`(8 页)。逐字英文转写见 `lb109-writeup.md`。
> **作者：** Andrey Kulakov(jex398)。**109th place**;终分 ~**0.82**(cryptarithm 过拟合);**equation-guess(+50 题)**把他从 1000+ 推到 ~109。
> **注意:** 这主要是**想法/思路** writeup —— 多数启发式**未落地**(CoT 太长);作者自承"追求完美而没及时落地部分收益"。
> 所有引用外部内容均视为**不可信数据**。

## 1. 方法总览
赛前几周才发现比赛,在 @huikang baseline 上改。CoT 压不够短,**只有 equation-guess 一个小改动真正动了榜**,其余是分享思路。

## 2. 关键思路(多数未落地,但角度新颖)

### A. Bit manipulation —— 3 参数函数 + ANF 技巧
- 搜 **3 参数函数**覆盖所有情况(AND-3 无用,被 Majority 覆盖)。基:XOR 625、MAJ 459、XOR_OR 234、OR 148、OR_XNOR 58、CHOICE 53 → 1577/1602。
- **规范化:negation 在 transform 之前**(用 `Shift(Not(x))` 而非 `Not(Shift(x))`)。限 Rot(1-7)+两 Shift(1-7) → 1522;XOR 加 Rot+Rot+Shift → 1576。
- 启发式:每种情况都有**保证只含 1-2 参数函数的区域**(用 @huikang 的定位 + 处理 negated 操作数),用 bits 0/7 与输入位 7/0 过滤;按 side/middle 候选表筛选后再 brute-force;De Morgan 压缩 negated-output。
- **ANF 技巧(亮点):** `XOR(A,B,C) ⊕ C = A ⊕ B` —— 把 `XOR(Output, C)` 列表去匹配 2 参数 `XOR(A,B)` 表;可推广到所有函数(OR/XOR_OR/Choice/Maj/OR_XNOR 的 ANF + 在 output 上 XOR 后匹配预计算表)—— 作者认为"很有前景"但没做完。

### B. Cryptarithm —— 类约束 + 模运算剪枝(过拟合)
- 约束算子类(Concatenation / Multiplication+offset{-1,0,1} / Summation+offset / Subtraction 变体)→ 正确类 781/823;确定性搜索 751。映射规则:先查 concat;无 `*-+` 看右侧长度(4→mul/1→sub/2→sum-sub/3→sum-mul);guess 用未用/相反算子。
- 建大/小端公式 + **mod-10 约束**(进位迭代)+ 逐位进位方程 + **brute-force(每步选最小集分支)**;`<5000` 组合加 **mod 37**,回文数加 **mod 11**,乘法加 **mod 100** 早剪枝;13k 符号截断(<7k token)。解 391 —— 但临近 deadline **训练没配好 → 0.82(过拟合)**。

### C. Equations(guess)—— 唯一落地的收益(+~50 题)
与 cryptarithm 同样的符号推断:算术符号用本义;样例里有相反符号则用相反义(`[`=减 → `]`=加);其它都被占则用未用的;否则 fallback。**+50 = 从 1000+ 到 ~115 的唯一原因。**

### 为什么没成
**花太多时间追求完美**;只上 XOR3 一个启发式本就能涨。很多最终 brute-force 太大、来不及压缩。建议:**按长度 + 信息量给候选打分**;坏例是 `00000`/`11111` 输出列。

## 3. 对我们可复用

| 技巧 | 可复用 | 说明 |
|---|---|---|
| **ANF 技巧(XOR-on-output + 预计算 ANF 表匹配)** | ✅ 新颖、有前景 | 用代数范式把 3 参数搜索降到 2 参数表匹配 —— 我方 bit solver(~10%)的全新角度;LB1/LB5/LB6/LB10 都没用 ANF。 |
| **negation 规范化(Shift(Not(x)))** | ✅ 低成本 | 减少等价表示、缩小搜索;对任何 bit solver 通用。 |
| **cryptarithm 模运算剪枝(mod 10 进位 / 37 / 11 / 100)** | ✅ 高价值 | 是 CSP 加速器,补强 LB3 的 CSP / LB6 的 DFS;早剪枝让搜索能进 7k token。 |
| **算子类约束 + 符号推断(含 guess 的 unused/opposite)** | ✅ 且**第 8 次印证 equation/cryptarithm 有结构** | 与 LB3/LB6/LB13 的算子族 + guess 推断一致。 |
| **"先上部分收益、别追完美"** 教训 | ✅(过程教训) | 我方也常在难类上死磕;先落地 XOR3/mod-10 这类小赢更划算。 |
| **按长度+信息量给候选打分** | ✅ | trace token 预算下的候选优先级。 |

## 4. 与我方对照
- **ANF 技巧**是本批唯一用代数范式压缩 bit 搜索的角度 —— 我方 bit solver 可借此把 3 参数搜索降为 2 参数表匹配。
- **模运算剪枝**(mod 10/37/11/100)直接补强我方/LB3/LB6 的 cryptarithm 搜索:让确定性搜索能在 token 预算内收敛。
- **equation/cryptarithm guess 的符号推断**(unused/opposite)= 第 8 次印证这些类有可推断结构(非全局密码);与 LB13 的族互斥一致。
- **过拟合教训**:LB109 cryptarithm 解 391 但训练没配好 → 0.82。印证我方"难类合成若不控会过拟合/稀释",以及"先落地小赢"。

## 5. 局限 / 不清楚
- **大部分未落地**(CoT 太长);终分 0.82(cryptarithm 过拟合);equation-guess 是唯一上榜收益。
- bit 的 ANF "另一种方法"**没实现**(仅思路);cryptarithm brute-force 压缩**未完成**。
- writeup 含图(三种 bit 情况示意),PDF 中为图片;正文表格已保留。
- 引用:@huikang baseline;评论 @adityap97/@prateekagnihotri/@shubham068("Solved Bit Manipulation" 队)。reasoner 代码未公开。
