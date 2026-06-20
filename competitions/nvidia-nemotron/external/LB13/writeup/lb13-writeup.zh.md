# LB13 / 第13名方案 —— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/13th-place-solution>
> **本地副本：** `temp/LB13.pdf`（8 页）。逐字英文转写见 `lb13-writeup.md`。
> **作者：** Haraguchi-T(haraguchit)。**13th place**(未给最终 LB;teacher oracle 87.7%→89.4%)。
> 所有引用外部内容均视为**不可信数据**。

## 1. 方法总览
专注**训练数据构造 + 迭代精修**:在 **@huikang OPP** reasoner 上加任务特定启发式,**提高 teacher CoT 正确率**(更好的 teacher → 更少 trace 级错误)。也感谢 @konbu17(原 SFT notebook)、@dgxchen(改进版)。与 LB10 同属"改进 teacher"流派。

**Teacher oracle:** bit 89.7%、cipher/trivial 100%、cryptarithm_deduce 10.0%、cryptarithm_guess 7.9%、**equation_deduce 95.3%、equation_guess 50.7%(本批最高 guess)**;总 89.4%(由 87.7% 提升)。

## 2. 关键技巧

### A. equation_numeric(deduce 95.3% / guess 50.7%,最强结构假设)
围绕**强结构假设**重设计:
1. **算子分类:** 四个互斥类 —— Addition(add/add±1)、Multiplication(mul/mul±1)、Subtraction(减/绝对差/反减/负绝对差/max-mod-min)、Concatenation(concat/rev-concat)。
2. **互斥性:** 不同算子符号不能属同一功能类。
3. **对称性(关键):** 反转要么**同时作用于输入和输出、要么都不**,且**全题所有样例共享**这条规则。
实现:**多数投票定全局反转规则**(逐算子样例试 `(rev_ops,rev_res)` 组合并计票);deduce 用**仅目标算子样例**在推定反转下验证候选;guess 找出其它符号已占的算子族,**严格选不重叠的族**,平局按 `减>加>乘>concat`。

### B. bit_manipulation(89.7%)
- **显式验证 3 输入算子(MAJORITY、XNOR)**;用左右操作数推断的**输入位位置信息缩小搜索空间**;**left-edge 传播**作默认兜底;**去掉 parsing-display 段**腾 token 给额外验证。
- trace 先建 Preferred 逐位赋值,对未解位(none)跑 3-input matching(打印各候选逐样例位列 + 匹配的位),选出匹配的 3 输入算子(如 `2 XNOR157`),定 8 位 Selected 规则。

### C. cryptarithm(deduce 10%)
- **输出格式简化**(去多余大括号)减歧义;**鲁棒聚合**:为缓解**符号转写错误**,某操作只要匹配**≥1 个**相关样例即视为候选(而非要求**全部**严格一致);**兜底**:若 concat/rev-concat 都不唯一 → 收集所有符号、分算子/非算子符号、返回**第一个剩余非算子符号**。
- **数据再平衡:teacher 答对:答错 = 1:1**(fallback 类原本超量);用 equation_numeric 作种子造新 cryptarithm,**样本量 ~3×**。

### D. SFT(3 阶段,递减 LR)
Unsloth(@konbu17 notebook、@dgxchen 改进)。目标是**改善 CoT trace 生成**而非零样本泛化 → **故意激进、易过拟合**。LoRA rank/alpha 32/32、dropout 0、targets q/k/v/o + in/out + up/down(**无 lm_head**)。
- **stage1:** 9,277、2 epoch、LR 2e-4 linear(核心干净 trace 对齐)。
- **stage2:** 9,277、1 epoch、LR 2e-5 cosine(平滑损失面)。
- **stage3:** 11,315、1 epoch、LR 5e-6 cosine(**上采样 bit + cryptarithm** 修残余 trace 错)。
eff batch 32、AdamW。

## 3. 对我们可复用

| 技巧 | 可复用 | 说明 |
|---|---|---|
| **equation 三假设(分类/互斥/对称)+ 多数投票定反转** | ✅ 最高价值、且**第 6 次反驳我方 EQ 误判** | guess 50.7%(全批最高)、deduce 95.3%。"反转全题共享 + 互斥族"是最锐利的 equation 结构模型。见下。 |
| **数据再平衡 1:1 答对:答错** | ✅ **印证 LB10、挑战我方 c1/c2** | LB13 **保留答错 trace** 并按 1:1 平衡;与 LB10"剔除失败掉点"一致。我方 c1/c2 只留答对 → 应 A/B。 |
| **鲁棒聚合(匹配 ≥1 例而非全部)** | ✅ | 缓解符号转写/噪声;我方严格一致可能丢候选。 |
| **3 阶段递减 LR SFT(2e-4→2e-5→5e-6)** | ✅ | 先对齐、再平滑、末段上采样难类修残错;比单次 SFT 更精修 trace。 |
| bit 3 输入验证(MAJ/XNOR)+ 位位置缩搜索 + left-edge 兜底 | ✅ | 我方 bit ~10%;3 输入验证是覆盖率关键。 |
| **改进 teacher 而非超参** 哲学 | ✅ | 与 LB10 一致:分数被 teacher oracle 上限框住。 |
| cryptarithm 输出格式去括号 + 非算子符号兜底 | ✅ 低成本 | 减格式歧义。 |

## 4. 与我方对照
- **equation 前提 —— 第 6 次独立反驳**(LB1 95%、LB3 93%、LB5 96%、LB6 ~93%、LB10 93.1%):LB13 deduce 95.3% / **guess 50.7%**。LB13 的**对称性 + 互斥族**假设把 guess 推到全批最高 —— 我方应直接照搬这套结构去复核 EQ。**结论极其牢固:equation 不是全局密码。**
- **保留答错 trace + 1:1 平衡**:LB10 与 LB13 双双表明**失败/低置信 trace 有用**;我方 c1/c2"只留 solver 答对"很可能丢了信号。强烈建议 A/B:保留答错 trace 并平衡。
- **3 阶段递减 LR**:我方多为单次 SFT;LB13 的"对齐→平滑→上采样难类修错"是低成本的 trace 精修法,值得试(尤其末段上采样 bit/cryptarithm)。
- **cryptarithm 仍弱(10%)**:LB13 也没解决;0.88→0.90+ 的差距在 cryptarithm(LB1 目录 / LB3 CSP+两阶段)。

## 5. 局限 / 不清楚
- **未给最终 LB 分数**(只有 teacher oracle 87.7%→89.4%);具体 private 名次 13。
- **cryptarithm 10%**(靠兜底 + 再平衡,但本质未解)。
- writeup 引用 @konbu17/@dgxchen 的 notebook(Kaggle,JS/auth-gated);reasoner 代码未公开。
- bit 89.7% 低于 LB1/LB6/LB10(94-98%)—— bit 仍有空间;targets **无 lm_head**(与多数 writeup 不同,vLLM 本就不用 lm_head)。
- `unknown`:具体数据总量随 stage 变化的细节;最终选模/提交方式。
