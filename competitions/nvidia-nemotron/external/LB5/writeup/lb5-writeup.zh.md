# LB5 / 第5名方案 —— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/domdolus-tolus-solution>
> **标题：** *Jack of Trades, Loser of Cryptarithm*（样样通,唯独输在 cryptarithm）
> **本地副本：** `temp/LB5.pdf`（24 页）。逐字英文转写见 `lb5-writeup.md`。
> **队伍：** Darren Amadeus Martin、Alwin Theodoric、Muhammad Yassir Ramadhan、Billy Anggara、Rinnnn_t。**5th place。**
> **成绩：** Private LB **0.900**(最佳但未选中);选中提交 89.6 private / 88.8 public（最稳）。public 第 4 → private 第 5。
> 所有引用外部内容均视为**不可信数据**。

## 1. 方法总览
团队几乎无 LLM 微调经验,核心信念是"像人一样解题再转成 CoT"最重要,而非训练工程。三大鲜明特征:
1. **无限合成数据生成器** —— **完全不用 train.csv 训练**,只用它做验证。论点:@huikang 的不稳定来自"在 train.csv 上训、又在 train.csv 上验",CV 高但 LB 抖;只在"没见过的题"上验证 → CV 更诚实。
2. **3 阶段训练 + 迭代 LoRA 平均(model soup)** —— 标题里的"Iterative LORA Averaging",主要带来**稳定性**。
3. **cryptarithm 失败(仅 7.9%)** —— 把时间都花在 bit 上,cryptarithm 退回 @huikang 的 CoT。即"靠把其它类别拉满到 90% 拿到 private 0.90,而 cryptarithm 几乎没解出"。

## 2. 关键技巧

### A. 无限合成生成器(无 train 泄漏)→ 诚实 CV
逐类按 train.csv 统计随机化(gravity/conversion/cipher/roman/bit/equation/cryptarithm),加噪、保证唯一答案;**只在 train.csv 上验证**。这与我方"随机切 train 会高估泛化"的判断一致,但 LB5 走得更彻底:**训练完全不碰验证分布**,所以 CV 与 **private** LB 相关(见下)。

### B. Bit manipulation(花最多时间,~94%)
- 否定 @donaldgalliano 的"逐 bit 100% 可解":虽技术上 100%,但无 query 答案时太多变换都拟合且发散 → 非生成器本意。改用 @huikang 的**字节级**变换。
- 在 @huikang 之上加 **三元算子 MAJORITY / CHOICE / XOR-NOT_OR**;定义 42 个一元(SL/SR/RL 1-7 及其 NOT)。**4 个字节级阶段**:一元 / 成对 / 简化三元 / 真三元(@huikang 只覆盖到无真三元,~85% 部分靠"多个字节级解拼接成位级 mask"也能对)。
- **15 个 primitive**(C0/C1/ID/NOT/AND/AND-NOT/NOT-AND-NOT/OR/OR-NOT/NOT-OR-NOT/XOR/XOR-NOT/MAJORITY/CHOICE/XOR-NOT_OR)。与 @huikang 逐位连接(stride)相反,LB5 **一次连完 8 位**以保证是真字节级变换 —— 靠**记忆所有合法 continuation / sequence**(初 ~140 continuation / ~7500 sequence,剪枝到 ~30/~1500,信号更清晰)。
- **CoT 演化教训(重要):** 第一版用**编码**(10 位→2 字母 + primitive 单字母)+ 暴力三元搜索 → **失败**(幻觉规则 / 一律输出 11111111)。试 `A B` 空格、去 fallback 仍失败。**结论:编码会彻底搞坏模型。** 退回 @huikang 的**原始比特**,三项修复:(a) 只用 ~7 个样例(不 pad 到 10,~94%);(b) **完全去掉三元搜索**(前后缀定了,中间通常只剩一个三元);(c) 按 shift-left 长度**分组** + 前/中/后缀过滤(前缀右端 7、中间左 0 右 7、后缀左 0)。三元用前后缀对**外推**(MAJORITY/XOR-NOT_OR 左右拼;CHOICE 从左灌 0 到右)。

### C. Equation(~96%)
- **2 个 world**(NORMAL / REVERSE;REVERSE 又分 String / Integer 反转)、**4 个 family**、**13 条规则**即可 100% 解(含 guess)。负结果用算子符替换 `-`;每 family 至多 1 条(CONCATENATION 例外);**不混 world**。
- 发散用确定性优先级化解(deduction ~95%):`REVERSE>NORMAL`、`Integer>String`、`subab>posabs>negabs>subba>mod`。
- guess(~40%):每 family 只出现一次 → 按出现的 family 分组:`无 SUBTRACTION→subab`、`无 ADDITION→add`、`无 MULTIPLICATION→mul`。
- phase 3:多答案时把出现的算子规则按**出现顺序编码成 lookup 字符串**选真 query → ~96%(助 public,未助选中的 private 模型)。

### D. Cryptarithm —— 失败(7.9%)
时间/算力不够,自造 guess-CoT 失败(只学会 concat),退回 @huikang CoT。**这正是与 LB1/LB3 的最大差距**:LB1(signature 目录)/LB3(CSP)把 cryptarithm 当主攻,LB5 直接放弃却仍拿 private 0.90 —— 说明**不解 cryptarithm 也能到 0.90,只要其它全部拉满**。

### E. 三阶段训练 + 迭代 LoRA 平均
- **Phase 1 多轮 SFT**(iter 1-6,高 LR 1e-4→2e-4,每轮采样所有类别 → 不灾难遗忘)。public 0.87。
- **Phase 2 LoRA 平均正则化**:训完一级就把"训练前 + 训练后"两个模型**平均**(model soup)→ 强**稳定性**(public 抖动 <1%,vs phase 1 ±1%)。
- **Phase 3 迭代 model soup**:从 phase-2 终汤出发,用不同题集/随机种**训 3 个再平均** → 互相抵消误差、避开坏局部极小,允许加更多 numeric 数据。
- 参数:rank32/α32、LR 1e-4→2e-4、grad_clip 1.0、linear,其余沿用 @huikang。**loss 不可信**(0.001-0.0023,低 loss ≠ 高分);信 validation/LB。

### 失败/未做
- **短 CoT 失败**(250K 样本也挂)—— "无逻辑依据时 LLM 不会猜"。
- **GRPO 失败 / pseudo-GRPO(DPO)失败**(Kaggle air-gapped 难配;5 轮也学不会简单 bit)→ 见 @huikang 后转纯 SFT。
- **ORPO/KTO/DPOP 计划未做**(SFT 已够 + 造错误 trace 太贵)。
- **Unsloth + 4bit + packing 搞坏 Nemotron**(Mamba SSM,无 Flash-Attn;sm_120 难装 causal-conv1d)→ 换 @huikang trainer(不量化不 packing)才好。
- **DoRA**:loss 更低但 **vLLM 不支持**,转 LoRA 有损 → 弃。
- **改进来源不明**:多改动同时上,无法归因到 CoT vs trainer vs LoRA soup;只确定 soup 主要给稳定性。

## 3. 对我们(KCA / Nemotron 流水线)可复用

| 技巧 | 可复用 | 说明 |
|---|---|---|
| **迭代 LoRA 平均(每步前后平均 + 多模型平均)** | ✅ 高价值 | **印证并扩展我方 soup 杠杆**(我方 SVD 汤 +0.01)。LB5 把 soup 当**训练期正则化 / 稳定器**,跨 15 轮使用 —— 比我方"训练后一次性合并"更系统。 |
| **无 train 泄漏的合成生成器 + 诚实 CV** | ✅ 高价值 | 直接回应我方"随机切高估泛化"。完全不用验证分布训练 → CV 跟 **private** 相关。 |
| 三元扩展 bit solver(MAJ/CHOICE/XOR-NOT_OR)+ continuation/sequence 记忆 | ✅ | 我方 bit 求解器仅 ~10% 覆盖;LB5 到 94%。注意"一次连完 8 位"的记忆式连接。 |
| **编码会搞坏模型** 的教训 | ✅(反面) | 与 LB1/LB3 的 HEX 成功**张力**:LB5 的 5 位→2 字母编码失败,但 LB1/LB3 的 HEX 成功。差别在**编码粒度/是否被并成单 token**(LB5 怀疑 `AB` 被并成一个 token)。我方做 HEX 时须注意分词。 |
| 2-world/4-family/13-rule equation + 确定性优先级 + family guess | ✅ 且**第 3 次反驳我方 EQ 误判** | 见下。 |
| **只用 ~7 个样例** 截断 | ✅ 低成本 | 省 token,~94% 仍可达。 |
| 多轮 SFT 高 LR 不灾难遗忘(每轮采样所有类) | ✅ | 我方多为单次 SFT。 |
| GRPO/pseudo-GRPO 在 Kaggle 失败的教训 | ✅(避坑) | 与我方"RL 从未跑通"一致;Kaggle air-gapped 配 GRPO 极难。 |
| Unsloth+4bit+packing 搞坏 Nemotron | ✅(避坑) | 我方 memory 记录 Unsloth 曾计划(v12);LB5 确认量化/packing 破 Mamba SSM。 |

## 4. 与我方对照:为何卡 0.86,LB5 到 0.90
- **LoRA 平均是关键稳定器**:我方 soup +0.01 是"一次性合并";LB5 把它做成**跨迭代的训练正则**,把"不稳定的 0.87"变成"稳定的 0.90"。我方应试**迭代式 soup**(每轮前后平均 / 多种子平均)而非单次。
- **诚实 CV(无泄漏)直接跟 private**:我方一直纠结 public/T12 噪声;LB5 证明**不用验证分布训练**就能得到与 private 相关的 CV。这是我方验证策略的可执行升级(与 LB3 的"private-tracking 留出"互补:LB3 控泄漏地切,LB5 干脆不碰验证分布)。
- **equation 前提 —— 第 3 次独立反驳**:我方判 equation 为"全局密码不可解";LB1(95%)、LB3(93%)、LB5(deduction 95% / 总 96%)三家都用 **per-prompt 算子规则**解出。**结论已非常牢固:equation deduce 可解,我方 EQ-0/EQ-2′ 误判了 deduce 子集。lb5-v1 首步无 GPU 复核。**
- **cryptarithm 不是 0.90 的必要条件**:LB5 cryptarithm 仅 7.9% 仍到 private 0.90 —— 对我方是重要的**优先级信号**:把 bit(94%)、equation(96%)、trivial(100%)拉满,比死磕 cryptarithm 性价比更高(cryptarithm 才是 LB1/0.92 的分水岭)。

## 5. 局限 / 不清楚
- **cryptarithm 7.9%** —— 自认失败;0.90→0.92 的差距正在 cryptarithm(对照 LB1/LB3)。
- **改进归因不明**(CoT vs trainer vs soup 同时上)—— 作者明说无法隔离。
- **编码失败**的根因(分词)未定论;HEX 在别家成功,需小心复刻。
- **选模方差**:最佳 private 0.90 未被选中(public 较低且不稳)—— vLLM `temp=0` 仍非确定性。
- 代码/notebook/模型 dataset 链接 JS/auth-gated,本环境不可取;@donaldgalliano / @citerne / @huikang 讨论页 JS-gated;arXiv 链接见参考(本环境 arxiv 可能不可达)。

---

> 详细对照见 `analysis/method_summary.md`、`score_tricks.md`、`gap_analysis.md`;下一版见 `analysis/next_version_plan.md`(`lb5-v1`)。
