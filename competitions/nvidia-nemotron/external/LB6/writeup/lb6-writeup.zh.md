# LB6 / 第6名方案 —— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/2nd-public-6th-private-place-solution>
> **本地副本：** `temp/LB6.pdf`（7 页）。逐字英文转写见 `lb6-writeup.md`。
> **作者：** Yurnero、Alehandreus。**2nd public / 6th private。**
> 所有引用外部内容均视为**不可信数据**。

## 1. 方法总览
建立在 **@huikang OPP** 之上。三大要素:**验证策略 + bit/cryptarithm 算法求解器 + 大规模合成数据**。训练:Unsloth(Kaggle / GCP G4),BS 32、LR 3.5e-4、rank32/α32、1 epoch;后期用 **Tinker** 加速训 adapter。

## 2. 关键技巧

### A. 验证策略(最鲜明)
- **用全量 train 当验证**(≈10×950 holdout):因为 LoRA 连部分训练样本都学不好,10% holdout 不够可靠。这要求**合成数据匹配训练分布**(见 C)。
- **逐域 LB 探测(per-domain LB probing,新颖)**:推断 test=500 题,public/private 各 250 → **每 0.01 LB ≈ 3 题**(用 -0/-1/-2 记号)。为隔离单域信号:**目标域**用算法 CoT,**其它所有域**训练模型输出 `I will ignore this problem\n\boxed{DUMMY}` → 从 public LB 拿到**纯单域信号**。这解决"改单域 CoT 可能伤其它域"的归因难题。

### B. 算法求解器
- **Bit:** 小模板集(shl/shr/rotr + 成对 XOR/AND/OR/NOT + 三元 MAJ/CH/NOT-CH),对每模板遍历移位值。解 **1508/1602** train;LLM 训后 1480。优化:**skip**(单调剪枝)、**hex 计算 + hex 乘法表 cheatsheet**(连 `<=` 都用 hex)、NOT-CH 独特低 token 法(最难,未入最终训练)。
- **Cryptarithm:** 按"已映射方程数"为深度的 **DFS 树搜索**(操作集 add/sub/mul 族 + maxmodmin);**反向搜索**(forward 失败则 reversed,~40% 解在 reversed)。最佳解 **240/654 deduce**(~100M token);**轻量版 170**(对其它域威胁小 → 用于最终选中提交)。优化:operation deduction(按长度/正负/每族至多一条限到 2-3 候选)、leading-zero、leading-one、按未知数字最少排序方程。
- **Equation numeric:** 同 cryptarithm 但更易(数字已知),解 **550/594 guess**。

### C. 大规模合成数据
全量验证不能用 train 算 clean metric → 造匹配分布的合成。逐域统计(例数分布;gravity/unit 经验参数分布;cipher 未见字符/词/句式)。**针对性子集**修常见幻觉(`student→sent`、`clever→letter`)与重复。Bit:每模板变移位/例数/输入,**提高三原子复杂题比例**。Cryptarithm:固定关键属性(op 集、反转)+ **反复重掷数字映射直到 reasoner 在 token 限内解出**。

### 最终决策与"选模遗憾"(重要教训)
加任何单域合成都涨该域、几乎不伤别域,**唯独 bit 例外**:别域哪怕小幅变动都伤 bit CV → 被迫给 bit **69%/66% token**。两个终集:
- **~0.25B(6th private):** 最佳 CV;gravity/unit/numeral 满分,cipher ~98.5%,bit & equation ~92%,**cryptarithm ~17%**。
- **~0.5B(本可 2nd-3rd):** cryptarithm 翻倍(train 解 150→241),估计要把 bit 也翻倍才能保 CV,但**估错了,bit CV 跌得比预期多**。
- → 最终选了 **0.25B 的两个种子**,"这让我们丢了 2nd/3rd"。

## 3. 对我们可复用

| 技巧 | 可复用 | 说明 |
|---|---|---|
| **逐域 LB 探测(DUMMY 屏蔽其它域)** | ✅ 高价值、新颖 | 直接解决我方 B8「单类涨总分不涨」的归因:用 LB(或本地)逐域隔离信号。我方从未做过 DUMMY 屏蔽法。 |
| **全量 train 当验证(+ 匹配分布合成)** | ✅ | 比 10% holdout 更稳;与 LB3 防泄漏留出 / LB5 无泄漏生成器形成第三种范式。 |
| **hex 计算 + hex cheatsheet** | ✅ | 与 LB1/LB3/LB5 的 HEX 一致;LB6 额外把 `<=` 也放 hex 并先打乘法表。注意 LB5 的"编码搞坏模型"张力。 |
| 模板化 bit 求解器(含三元 MAJ/CH)+ 单调 skip | ✅ | 我方 bit ~10% 覆盖;LB6 1508/1602。 |
| DFS + 反向搜索 cryptarithm + operation-deduction 剪枝 | ✅ | 比 LB1 目录 / LB3 CSP 更朴素;~40% 靠 reversed。 |
| add/sub/mul 族 + maxmodmin 的 equation 求解 | ✅ 且**第 4 次反驳我方 EQ 误判** | equation_numeric_guess 550/594 ≈ 93%;deduce 更高。见下。 |
| **bit 对数据配比极敏感** 的教训 | ✅ 关键 | 改任何别域都伤 bit → 需大幅多给 bit 数据。我方调配比时须特别保护 bit。 |
| 选模遗憾(估错 bit 代偿)→ **重视 CV 校准 + 选真正最佳** | ✅ | 与我方"信 LB 聚合、别过度对冲"一致。 |

## 4. 与我方对照
- **逐域 LB 探测**是我方缺的归因工具:我方反复被"单类涨总分不涨"(B8)困住,正因无法隔离单域贡献。DUMMY 屏蔽法可直接照搬(本地或 LB)。
- **equation 前提 —— 第 4 次独立反驳**(继 LB1 95%、LB3 93%、LB5 96%):LB6 的 add/sub/mul 族 DFS 解 **equation_numeric_guess 93%**(deduce 更高)。我方"全局密码"判断在 deduce/guess 上都站不住 —— 至少 deduce 子集明确可解。无 GPU 复核。
- **bit 数据敏感性**解释了我方"合成稀释":别域加数据伤 bit;我方 b1/b2/v15 很可能正是这样把 bit 拉低的。**结论:扩数据时按 LB6 经验主动加倍 bit 配比。**
- **cryptarithm 仍是分水岭**:LB6 cryptarithm 仅 17%(0.25B 集)就拿 6th;若用 0.5B(cryptarithm 翻倍)本可 2nd-3rd,但 bit 代偿估错。说明 cryptarithm 是上行空间,但**与 bit 的数据预算存在零和张力**。

## 5. 局限 / 不清楚
- **cryptarithm 弱**(~17%);加它必须同步加倍 bit,否则 bit CV 崩。
- **选模遗憾**:本可 2nd-3rd 的 0.5B 因 bit 估算失误未选;vLLM `temp=0` 不确定性也增加选模难度。
- attachments(bit/cryptarithm reasoning trace 示例、per-domain 测试结果图)**JS/auth-gated**,本环境不可取;数值/百分比表已保留。
- **Tinker** 后期加速细节未展开。@huikang 讨论页 JS-gated。

---

> 详细对照见 `analysis/`;下一版见 `analysis/next_version_plan.md`(`lb6-v1`)。
