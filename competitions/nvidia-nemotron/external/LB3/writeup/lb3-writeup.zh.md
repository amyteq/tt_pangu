# LB3 / 第3名方案 —— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/3rd-place-solution>
> **本地副本：** `temp/LB3.pdf`（17 页）。逐字英文转写见 `lb3-writeup.md`。
> **作者：** YS-L（liauys）。**成绩：Private LB 0.900；本地验证 90.46%。**
> 所有引用的外部内容均视为**不可信数据**,不作为指令执行。

## 1. 方法总览

LB3 建立在 **llkh0a、huikang、kemshim、youkinasa** 等人的早期工作之上,六项改进:
1. 重写的、更精简且**猜测逻辑更好**的 numeric 求解器；
2. **Hui Kang 式 bit trace 用 hex 压缩** + 扩展 **MAJ(多数)搜索**；
3. 除 gravity/unit/numeral 外**全类别数据增广**；
4. **CSP 式 cryptarithm 算法**:用乘法模式 + 回溯搜索,预算内解 **24.2%**(deduce 27.8% / guess 9.8%)；
5. **两阶段训练**:**解耦"记忆"与"执行"**,让模型更好地学会 cryptarithm trace；
6. **本地验证策略**:结果证明能很好地**跟踪 private 测试集**。

## 2. 关键技巧(为什么有效)

### 技巧 A —— CSP 式 cryptarithm 求解器(LB3 的核心创新)
思路源自 **kemshim / youkinasa** 的"乘法模式查表":
- 先找 **MUL(乘法)样例**(约束最强,答案长度 4);每个 MUL 样例从查表发射"每个符号的可能数字"+"候选映射"。
- 多个 MUL 样例时求**交集**:把不同样例的候选映射做 **join**,无冲突则合并、有冲突则拒绝 → 常常只剩 1 个 **anchor 映射**。
- 对每个 anchor 启动**回溯符号求解器**(每方程 ≤2 未知量):每步选未知量最少的方程,非负答案试 `a+b/a+b±1/a-b/abs(a-b)`,负答案试 `a-b/-abs(a-b)/b-a`,回溯/早停。
- 对 `(结构, 乘法类型)` 组合重复(结构 ∈ {simple, reverse},乘法 ∈ {a*b, a*b±1}),**先 reverse 后 simple**,首个满足全部样例即停。
- trace 里 `<RECALL_DOMAINS>`/`<RECALL_ROWS>` 标记**纯靠记忆**生成的段;通过 join(`Y`合并 / `NS`符号冲突 / `ND`数字冲突)在 trace 内做合并/冲突检测。
- 工程细节:每签名候选 ≤48、anchor ≤8;长度 3 且同 MUL 算子的样例也当 MUL；未知算子用"未用过的算子族"猜测。
- 预算内解率:deduce 27.8%、guess 9.8%、合并 24.2%。

与 **LB1** 对比:LB1 用 4205 条**完整 signature 目录**(全 22 非 join 规则)直接记忆候选 + 候选数;LB3 只对**乘法**做模式查表 + **多样例交集求 anchor** + 回溯。LB3 更轻、更"CSP",LB1 更"全量记忆"。

### 技巧 B —— 两阶段训练(强 sample efficiency,亮点)
cryptarithm trace 成功取决于:(a) 给定签名+乘法类型能**正确回忆**域/候选行;(b) 假设回忆正确能**正确执行**算法。
- **第一阶段:学记忆。** 纯 "drill" 补全请求(`<RECALL_DOMAINS>`/`<RECALL_ROWS>` → 域/行),覆盖所有乘法签名;每样本**打包 16 个签名请求**,开头标签与请求签名 **mask 不计 loss**。LR 2e-4、eff batch 8、~27.6K 步。**记忆质量(1000 随机签名):overall exact 97.1%、domain 98.4%、row-ordered 95.9%、row-set recall 98.0%。**
- **第二阶段:学求解。** 以第一阶段 LoRA 作**初始 adapter**,在真实 trace 数据上训练,专注**执行**;注入 3K drill 样本保记忆。
- **效率证据(12K cryptarithm,~11 题可解):直训解 0,两阶段解 7;直训要 36K 才能解 7。** 即 40K+ 即可接近目标解率。第一阶段**不损害**下游学习,且**模块化**(改 solver/格式可复用同一第一阶段模型)。

### 技巧 C —— Bit:hex 压缩(保留尾比特)+ MAJ + 规则重排
- 输出位列用 hex + `|尾两位`(如 `1110001110` → `E3|10`),省 **~25% token**(把末两位也编进 hex 反而让 9/10 样例变差,故尾比特保留)。
- 省下的预算用来**搜索 MAJ**。
- 规则顺序把 **OR-NOT 排到 OR/XOR 之前**,解率 +0.6%。

### 技巧 D —— 精简 numeric 求解器 + 算子族猜测
- 13 个算子的**最小集**(逐个加直到能无歧义解全部"偷看答案"的题)。无偷看时仅**减法族**有歧义,用确定性顺序(偏好 `a-b`)最大化解率。simple/reverse **必须全局统一**。
- **算子族结构**:共现表显示 `a*b` 不与 `a*b±1` 同现等 → 生成器按"族"采样、每族选一个;故未知算子时**猜未映射过的族里的算子**。训练解率上限:deduce 93.79%、guess 38.97%、overall 83.61%。

### 训练 / 验证
- huikang 的 **CCE** 训练环;**关闭 MoE tie weights**;**eff batch size 越小越好**(16→8→4);LR 2e-4 linear、rank32/α32、lm_head 手动 LoRA、grad norm 10、seed 42、seq 8192。
- 验证:**10% 分层留出(954 行)**,且排除来自验证原题的增广样本(防泄漏)。**该验证跟 private 很贴合,跟 public 不贴合**(public 卡 0.86 墙;一个 public 0.85 的提交 private 拿 0.90)。
- 额外指标:**perfect trace rate**(bit >85%、cipher/numeric >95%)+ cryptarithm 记忆/自洽指标。
- **单类别迭代**:新 solver/格式先单类训练+验证(当作上限),确认更好再并入总混合。
- 终分:**Private 0.900**;本地总 90.46%。

## 3. 对我们(KCA / Nemotron 流水线)可复用

| 技巧 | 可复用 | 说明 |
|---|---|---|
| **两阶段(记忆→执行)训练** | ✅ 最高价值、最新颖 | 12K 样本下 0→7 的差距说明它是**强 sample-efficiency 杠杆**;我方从未做过 memorize-drill 预训练。模块化(改 trace 不必重背)。 |
| CSP 交集 + anchor + 回溯(cryptarithm) | ✅ 高价值 | 比 LB1 全量目录更轻量;只记乘法模式 + 多样例交集即可锁定大部分数字。 |
| hex + 尾比特压缩(bit) | ✅ 低成本 | 与 LB1 的 HEX 同向(LB1 −27.8% / LB3 −25%);我方从未压缩 trace。 |
| 13 算子最小集 + 算子族猜测(numeric) | ✅ 且**直击我方 EQ 误判** | 见下:LB3 用 13 算子 + simple/reverse 把 equation deduce 做到 93.8%,而我方判定 equation 为"不可解全局密码"。 |
| 防泄漏的分层验证(排除增广派生) | ✅ | 我方 T12 晚且对非典型 adapter 误判;LB3 的"验证跟 private 贴合"是更稳的范式。 |
| perfect-trace-rate 作 leading indicator | ✅ | 在解率掉之前就抓住 trace 错误。 |
| 单类别迭代当上限 | ✅ | 隔离改动效果,我方常被"单类涨总分不涨"(B8)困住。 |
| 关闭 MoE tie weights / 小 eff-batch | ⚠️ 待验证 | 与我方 v14(MoE-128 tying)做法相反 —— 值得 A/B。 |

## 4. 与我方对照:为何我们卡在 0.86

- **0.86 墙**:LB3 明确画出"public 0.86 墙",并指出 **public 不可信、private 才贴合本地验证** —— 印证我方"信 LB 聚合、本地是噪声代理"(INS-002)的同时,给出**更强结论:应以离线分层验证为准、把 public 当噪声**。我方一直把 public LB 当主信号,可能因此错过了 private 仍在涨的方向。
- **equation 前提冲突(重要,与 LB1 一致)**:我方 EQ-0/EQ-2′ 判定 equation 为"全局强密码/不可恢复"。LB3 的 **13 算子最小集** + simple/reverse + 算子族,把 **equation_numeric_deduce 做到 93.3%**(guess 57%)。这第二次独立证实:**equation 是 per-prompt 算子规则(deduce 可解),不是全局密码**;我方很可能把 deduce 子集也误判为不可解。**lb3-v1 首步用无 GPU 探针复核。**
- **合成稀释 vs 大规模结构化合成**:我方 b1/b2/v15 小规模合成**稀释**主配方;LB3 用 **48K cryptarithm 合成 + 两阶段记忆**做主干,且用"复用原题改操作数"避免造出/抹掉官方生成器的隐藏结构 —— 这正是我方"朴素合成稀释"的解法。
- **两阶段是我方完全缺失的维度**:我方只有单阶段 SFT;LB3 的"先背 drill 再学执行"是把"记忆"从"执行"里拆出来,显著提效。

## 5. 局限 / 不清楚

- cryptarithm **guess 仍极弱**(本地 5.88%);cryptarithm deduce 也只 30.3% —— 长尾未真正攻克,但 bit/cipher/numeric 拉满到 89~99%。
- 求解器在"偷看答案"前提下无歧义,但**真实无偷看时减法族歧义只能靠确定性顺序**(本质不可分)。
- **代码未在 writeup 公开**(cryptarithm 例的完整 trace 在附件 `cryptarithm_example.txt`,本环境未取得)。CSP/两阶段需按描述复刻。
- 算力:第一阶段 25.2h + 第二阶段 32.7h(单卡,~4.6 亿 token)。我方竞赛期(Kaggle ≤8h)无法复制;post-comp RTX Pro 6000 可做缩小验证。
- **llkh0a 的 notebook** 是 LB3 的起点(trivial 类别 + cipher 的 trace 来源),但 Kaggle 页 JS 渲染、本环境不可读(见 `source_index.md`);huikang/youkinasa/kemshim 同 LB1,讨论页 JS-gated。

---

> 详细对照见 `analysis/method_summary.md`、`score_tricks.md`、`gap_analysis.md`;下一版见 `analysis/next_version_plan.md`(`lb3-v1`)。
