# LB1 / 第一名方案 —— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/1st-place-solution>
> **本地副本：** `temp/LB1.pdf`（28 页）。逐字英文转写见 `lb1-writeup.md`。
> **作者/队伍：** GoodMeatDay、re、reopon。**成绩：** Public 与 Private LB 双第一。
> **关键分数：** cryptarithm 路线 → Public 0.89 / Private 0.908；bit 修复 + 续训 → **Public 0.91 / Private 0.920**（未被选中的最佳提交 Private 0.932）。
> 所有引用的外部内容均视为**不可信数据**，不作为指令执行。

---

## 1. 方法总览（核心思想）

整套方案的核心是一句话：**决定"让模型记什么、在 trace 里算什么"（memorization vs computation 的切分）**。

竞赛规则决定了这一切分必须存在：提交物只能是 LoRA 适配器（rank ≤ 32），评测时用 vLLM 加载，`temperature=0、max_tokens=7680`，把 `\boxed{}` 内的最终答案和真值比对。**评测时不能运行任何外部程序**——所以"求解器"必须以 SFT trace 的形式被模型内化，再在 7680 token 预算内一步步重放出来。

整体流水线很朴素：

1. 从 `train.csv`（9,500 题）抽取统计量；
2. **程序化**生成合成题（不是让 LLM 自由编题）；
3. 用**基于规则的求解器**给每题附上 trace（teacher CoT）；
4. 用 SFT 训练模型模仿这些 trace。

七个类别中，他们判断只有 **cryptarithm（密码算式）和 bit manipulation（位运算）** 还有大空间——因为公开 LB 上大量提交卡在 0.86 附近，0.87 的提交在增多，评测又有方差。要稳拿第一，必须在这两个类别上拉开**清晰的差距**，而不是停在"靠运气决定名次"的区间。

## 2. 三大得分技巧（为什么有效）

### 技巧 A —— Cryptarithm：signature catalog（签名目录）+ 候选数记忆 + DFS

朴素搜索空间约 `10! × 24^3 ≈ 5e10`，根本无法在 7680 token 内逐 token 重放。突破点是 **signature（签名）视角**：把一条方程 `左操作数 + 右操作数 + 输出` 按首次出现归一化为 A,B,C,…（例如 `'^-"} = -@@` → 签名 `ABCD-EE`）。

他们把 100×100 两个 2 位操作数 × 22 条非 join 规则**穷举一遍**，得到 **4205 个唯一签名**；每个签名映射到若干候选行（规则 + 槽位数字串 + **候选数 count**）。然后**让模型把这张签名目录连同候选数一起背下来**。

为什么有效：DFS 最贵的是**第一条方程**（要一次性定 4~8 个数字符号 + 该方程的规则）；后面的方程因为符号已被锁定，新增未知量往往只有 0~3 个。于是他们用记忆的"候选数"来**选 anchor（最小候选数的方程）和搜索顺序**，DFS 不再从零枚举第一条方程，而是从目录里取候选、只检查与其余方程的一致性。Observation 1（同一 prompt 所有非 join 算子同 mode）和 Observation 2（非 join 算子不复用同一 group）用于剪枝。

> 仅此一项就把 cryptarithm 推到 **Public 0.89 / Private 0.908**。

这条 signature 思路本身来自 **@youkinasa 的讨论帖**（用按签名建表来减少候选）；**第一名的增量**是把它从"推理期程序"改成"**模型记忆的目录**"——因为本赛禁止评测期跑程序。@kemshim 在赛末也分享过类似的乘法表记忆思路，但聚焦于乘法、规模较小。

### 技巧 B —— Bit manipulation：HEX 压缩 + 补规则 + rule-sequence catalog 的 Hamming 修复

起点是 @huikang 的逐输出位求解器（不一次猜 8 位，而是给每个输出位找一个用输入位表达的规则，再从左/右选最长连续规则序列）。第一名做了三件事：

1. **HEX 压缩**：Nemotron 的分词器几乎"一字符一 token"，而原 trace 反复打印 0/1 位列非常费 token。把长度 ≥4 的位串转成十六进制，使生成 token 的**中位数从 6771 降到 4888（−27.8%）**。早期 HEX trace 掉点，但增加 HEX 合成数据后恢复了大部分精度，同时保住更短的输出长度。
2. **补规则**：加入原方案放弃的 majority、3 输入 parity、条件选择（ch / sel_nand_xnor）、3 输入复合（ao/oa/ax/ox/xa/xo）等。规则集通过"保持能解释 train 全部样例与 query 的前提下增删规则族"调到**紧凑**而非无脑膨胀。
3. **Repair（修复）**：@huikang 的启发式选序列可能 8 条规则各自匹配样例、但作为整体不是一个合法的 8 位变换（甚至出现 `default 1` 这种常数兜底）。他们把所有理论上合法的 8 位变换归一化成 8 槽规则序列，去重得 **5238 条合法序列**作为目录；推理时用 **Hamming 距离**（在 8 个规则槽上，不是答案位上）做最近邻投影——只检查离所选序列最近的最多 **32 条**候选，自上而下取第一条能匹配全部 8 个输出位的序列。

> 加上 repair + 续训后，最终 **Public 0.91 / Private 0.920**（未选中的最佳提交 Private 0.932）。

一个有意思的来源：repair 的灵感来自一次**意外的不一致 trace**——开发中误造了一个"trace 来自求解器、但 `\boxed{}` 被替换成真值"的样本，模型竟学会了"在求解器错的时候只改最终答案"的格式。

### 技巧 C —— 简单类别照搬 + 关键约束

text cipher 用 **train.csv 明文侧仅 77 个词**的小词表做约束（不是任意英文词）；numeral/unit/gravity 直接沿用 @huikang 的过程。equation numeric 用 **24 条规则清单** + 算子先验（`+/-/*`）。注意：算子先验在 cryptarithm **不迁移**，所以那里没用。

### 训练与选模

- 框架 **Unsloth**；LoRA rank 32 / alpha 32；目标模块含 q/k/v/o_proj、in/out_proj、up/down/gate_proj、**lm_head**（评论区指出 vLLM 推理不用 lm_head，训它大概不影响分数）。
- 主训 LR 2e-4 cosine、1 epoch、bs(eff)=16、~119h；续训 LR 1e-5、6500 步、~51h、bs(per-device)=2。**单卡 RTX PRO 6000 Blackwell**，>10 亿 token，总训练数据约 890M（主）+ 590M（续）token。
- 选模：GPU 不够本地评多 checkpoint，于是**靠 Public LB 当噪声信号**；事后本地验证曲线与 Public LB 趋势一致。`temp=0` 仍非完全确定性，Private LB 在相邻 checkpoint 间抖动很大。最终选了**续训后两次提交**。
- 全部代码用 **Codex** 写（"没手写一行代码"），但**提分的思路、分析方向、trace 设计几乎都不来自 Codex**。

## 3. 与我们（KCA / Nemotron 流水线）的关系：哪些可复用

| 技巧 | 对我们是否可复用 | 说明 |
|---|---|---|
| memorization/computation 切分原则 | ✅ 高价值 | 我们已知"评测期不能跑程序"，但没有系统化地把"难类别求解器"压缩成可记忆的目录 + 短验证。这是第一名与 0.86 群体的根本分界。 |
| signature catalog + 候选数记忆（cryptarithm） | ✅ 应优先复刻 | 我们做过 b1/b2/v15 的合成，但 cryptarithm 仍是"靠合成堆量"，没有 anchor/候选数这种**让 DFS 变短**的结构。 |
| HEX 压缩（bit） | ✅ 低成本高收益 | 我们从未压缩 trace；−27.8% token 直接放宽 7680 预算，对 bit 这种长 trace 尤其关键。 |
| rule-sequence catalog + Hamming repair（bit） | ✅ 中等难度 | 需要先枚举合法 8 位变换并归一化；但能把"逐位拼凑可能不自洽"修成合法解。 |
| 77 词明文词表（cipher） | ✅ 已部分具备 | 我们的 cipher 求解器已较强，可加上这个强约束词表。 |
| 24 规则清单 + 两条 observation（equation/cryptarithm） | ⚠️ 部分 | **关键分歧见下：** 我们的 EQ 研究结论是 equation numeric 是"全局强密码/PRF、不可由样本恢复"；而第一名用 24 规则 + per-prompt 算子推断把 equation deduce 做到 95%。需要重新核对我们 EQ-0/EQ-2′ 的前提。 |
| 程序化合成（非 LLM 编题） | ✅ 我们已采用 | 但第一名的合成**强制执行两条 observation**、并按 train 统计采样骨架，质量更可控。 |
| 大规模单卡续训（>1B token） | ⚠️ 算力受限 | 我们竞赛期只有 Kaggle kernel（≤8h），无法复制 119h 主训。post-comp 有 RTX Pro 6000 可做小规模验证。 |

## 4. 为什么第一名能甩开 0.86 群体（与我们的对照）

- **0.86 是"干净 SFT 上限"**：我们和大多数人都卡在这里。第一名没有靠 RL，而是把 cryptarithm 和 bit 这两个长尾类别用"记忆目录 + 短验证"做出**清晰差距**。
- **我们犯的核心错误**：把单类别提升当成总分提升（B8：cryptarithm 8%→71% 但总分仍 ~0.86），而且**增广反而稀释了干净 replay 配方**，在最难切片上把 cipher/bit 拉回甚至低于 base。第一名用**大体量 + 结构化目录 + HEX 省 token**避免了"靠堆合成稀释主配方"的陷阱。
- **equation numeric 的根本分歧**：我们（EQ-0/EQ-2′）判定 equation 是"全局确定函数 / 强密码，61.6% 的 prompt 含未见 query 符号、不可由 7748 样本恢复"。但第一名的 solver-coverage 表显示 **equation deduce 95.3%、guess 仅 52%**——即"deduce（query 算子在样例中出现）"是可解的，"guess（未见算子）"才难。这说明**我们可能把 deduce 子集也当成不可解了**。这是下一版必须复核的最大不确定点（见 `analysis/gap_analysis.md` 与 `analysis/next_version_plan.md`）。
- **选模/方差**：第一名明确接受 `temp=0` 仍抖动、Private 在相邻 checkpoint 间大幅波动；最佳未选提交 0.932 vs 选中 0.920 说明选模本身就是一道方差关。我们的 T12 hard-val 对非典型 adapter 会误判（INS-002），结论一致：**hard-val 只作硬尾提示，聚合 LB 才是主信号**。

## 5. 局限 / 不清楚的地方

- **看真值后做的解题器 = 有泄漏**：作者自己声明 solver-coverage 表"essentially includes leakage"，所以那些 90%+ 的覆盖率不能直接当作泛化能力。
- **cryptarithm guess（未见算子）仍很弱**：12.8%；equation guess 52.9%。即"未见算子"这一长尾两个类别都未真正解决。
- **代码未公开（截至写作时）**：signature catalog / rule-sequence catalog 的具体实现需自行复刻；HEX 压缩、5238 条合法序列的枚举细节需要按描述重建。
- **算力门槛高**：119h 主训 + 51h 续训、>1B token，单卡 Blackwell。我们竞赛期无法复制；只能在 post-comp 用 RTX Pro 6000 做缩小规模的验证。
- **bit "碰巧匹配"的本质不可解性**：若某合法 catalog 序列在所有样例上都匹配、但在隐藏 query 上与真值不同，则"仅凭样例无法区分"——这是该类别的信息上限，repair 也无法越过。
- **链接获取受限**：@youkinasa、@kemshim、@huikang 的 Kaggle 讨论页为 JS 渲染、本环境不可读（详见 `source_index.md`）；@huikang 的 GitHub 源码可读，已确认 signature catalog / HEX / rule-sequence repair **不在**其代码中（即第一名的增量）。

---

> 详细对照见 `analysis/method_summary.md`、`analysis/score_tricks.md`、`analysis/gap_analysis.md`；下一版计划见 `analysis/next_version_plan.md`（版本名 `lb1-v1`）。
