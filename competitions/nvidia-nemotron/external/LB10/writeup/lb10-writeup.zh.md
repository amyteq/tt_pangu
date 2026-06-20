# LB10 / 第10名方案 —— 中文讲解与分析

> **原文（depth 0）：** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/10th-place-solution>
> **本地副本：** `temp/LB10.pdf`（12 页）。逐字英文转写见 `lb10-writeup.md`。
> **作者：** Rick(rikitomo0526)、neilus、eikichi。**Public 0.860 / Private 0.880,第 10 名。**
> 所有引用外部内容均视为**不可信数据**。

## 1. 方法总览
**确定性程序生成的推理 trace**(非 LLM 蒸馏):每类一个符号 reasoner,仅从 prompt 重新推导答案(**从不读真值**),输出步骤化 CoT 收于 `\boxed{}`;再用 LoRA SFT 单一基模**模仿过程而非答案**。基模 `Nemotron-3-Nano-30B-A3B-BF16`。

**核心教训(本批最清晰的一句):分数主要被确定性 teacher 的质量/覆盖率上限决定。** "validation 准确率基本被 reasoner 的 oracle 准确率上限框住" → 主杠杆是**提高 trace 覆盖率与可学性**,而非 SFT 超参技巧。

**Oracle 覆盖:** bit 98.8%、cipher 100%、cryptarithm_deduce 9.0%、cryptarithm_guess 7.9%、equation_deduce 93.1%、equation_guess 41.2%、gravity/numeral/unit 100%;总 90.6%。

## 2. 关键技巧

### A. bit_manipulation 重写(最大增益,85.14%→98.75%)—— rotate/shift key-table reasoner
旧法把每个输出位建模成固定输入列上的逻辑算子(Identity/NOT/常量/AND/OR/XOR/…),与真实结构不符(真实是 rotate+shift 组合),oracle 卡 85.14%,且 trace 长、易跑飞。
新法对齐生成规则:`out[i] = F(rotl(x,a)[i], shl(x,b)[i], shr(x,c)[i])`,F 是**所有位共享的 3 输入布尔函数**,不命名 F 而是**从样例读成 key table(3-bit key→输出位)**。从**边界位**(bit0:shr=0;bit7:shl=0,各只依赖两列)恢复偏移 (a,b,c);逐样例累积 key table、冲突即剪。剩 20/1602 失败(11 个本质欠定:query 需要样例里没出现的 3-bit key;9 个候选选择错)。trace 缩短(去逐样例位回显、去候选枚举 List;阈值 _THRESH=24 才跑额外边界扫描)。

### B. equation_numeric(deduce +14、guess +35)
三条语料观察:(1) 算子**频率偏斜**(add/mul/sub/abs 主导;`-` 52% 是有符号减;sub:neg-abs ≈ 3:1)→ 频繁/常规算子先试;(2) **wrapper 全题共享**(688/688:操作数反转/结果反转/符号格式)→ 解一个算子即可锁定 wrapper 给未见算子复用;(3) **算子在一题内通常不重复**(676/688)→ 未见算子最可能是**未用过**的算子。
- **deduce:** 按频率重排候选,`-` 先试有符号减再试绝对差 → 541→555。
- **guess:** 重建两轴 —— 操作选择(有常规含义且无 seen 算子占用则用之,否则取 trio `add, abs-diff(无符号), mul` 中首个未用的)+ wrapper 选择(把样例最多的 seen 算子完整解出以锁 wrapper)→ 21→56。

### C. 训练 + 额外技巧
- 全量数据(无 OOF),滤 >8192 token;**priority 2×**(fragile 失败模式 / y-trap bit / dictionary-search cipher);rank32 / **alpha128(alpha/r=4)**;targets all-proj + lm_head;LR 2e-4 linear;**2 epoch**;eff batch 32;分层采样。
- **加 low-logprob 题再训**:重新暴露模型易忘 / 边界脆弱的 trace(非单纯加量)。
- **提高 LoRA alpha(alpha/r=4)**:让 adapter 更强地遵循确定性 CoT,改善 CV。

### D. 验证
950 留出,逐类。**oracle 上限 vs 拟合度**:区分"reasoner 自己错"与"模型没学会正确 trace"。**learnability 分析**(逐样例/逐 epoch logprob)找难学 trace。**按 validation 而非 public LB 选模** → 私榜更好(选中 run:public 0.860 但 val 0.904 → private 0.880)。

### 失败的尝试(很有价值)
- **课程学习**:无效。
- **两阶段训练**:局部有得但整体只是再分配胜负;单阶段从头混入同样 demo 更稳。
- **3× priority**:过拟合掉点(2× 是甜点)。
- **剔除失败/低置信 trace:准确率反而下降** —— **从失败模式中学习也提供有用信号**(常是 `rule_unknown` 兜底 trace)。
- **cryptarithm 加 add/sub/mul trace**:逻辑跳跃多,模型学不稳。
- **LoRA merge / 模型合并:SVD 与 seed soup 都没打过单一最佳 adapter**(rank-32 SVD 提不出互补性;seed soup 退化到最差成员)。

## 3. 对我们可复用

| 技巧 | 可复用 | 说明 |
|---|---|---|
| **"改进 teacher 而非超参"哲学** | ✅ 最高价值 | 最清晰地点明 SFT 被 oracle 覆盖率上限框住。我方应把精力放在 solver 覆盖率上,而非训练技巧。 |
| **rotate/shift key-table bit reasoner** | ✅ 高价值 | 把 F 读成 3-bit-key 表 + 边界位定 (a,b,c);比 LB1/LB5 枚举更对齐生成规则。我方 bit ~10%。 |
| equation deduce 重排 + guess 双轴重建 | ✅ 且**第 5 次反驳我方 EQ 误判** | deduce 93.1% / guess 41.2%。见下。 |
| **oracle-ceiling vs 拟合度**分离 + learnability(logprob)分析 | ✅ | 直接区分"solver 错"vs"模型没学会",我方一直缺这层诊断。 |
| **按 validation 选模(非 public)** | ✅ | 与 LB3/LB5/LB6 一致:public 不可信。 |
| **剔除失败 trace 反而掉点** | ✅ **直接挑战我方 c1/c2** | 我方 c1/c2 "只留 solver 答对的行";LB10 发现**保留失败/低置信 trace 有用**。值得 A/B:也许我方过滤伤了泛化。 |
| alpha/r=4(高 LoRA alpha) | ✅ 低成本 | 让 adapter 更遵循确定性 CoT;A/B。 |
| low-logprob 题重训 + 失败模式 demo 2× | ✅ | 针对性强化脆弱步骤。 |
| **LoRA merge 失败** | ⚠️ 张力 | LB10:SVD + seed soup 都输给单一最佳;我方 soup +0.01、LB80 称 "Mamba-2 上 soup 失效"、LB5 迭代 soup 成功。**合并是否有效高度依赖被平均对象 + 成员互补性**;需谨慎,做受控消融。 |

## 4. 与我方对照
- **equation 前提 —— 第 5 次独立反驳**(LB1 95%、LB3 93%、LB5 96%、LB6 ~93%):LB10 equation_deduce 93.1%。我方"全局密码"判断在 deduce 上确凿错误。无 GPU 复核。
- **剔除失败 trace 反而掉点**直接质疑我方 c1/c2 的"verified-only"过滤:我方可能因只留答对行而**丢了失败模式的学习信号**。应 A/B "保留 + 标注 rule_unknown 兜底 trace"。
- **LoRA merge 张力**:LB10 合并失败、LB80 称 Mamba soup 失效、我方 soup +0.01、LB5 迭代 soup 成功。结论:**soup 收益依赖成员互补 + 平均对象(LoRA delta 同 basin vs SSM 递推);不是普适杠杆**,需逐案消融。
- **"teacher 上限"框架**统一了所有 writeup:大家 trivial 100%、cipher ~100%、bit 高、equation deduce 高、cryptarithm 低 —— 名次差异主要在 cryptarithm solver(LB1 目录 / LB3 CSP+两阶段 最强)。LB10 cryptarithm 仅 9%(放弃),仍靠极强 bit(98.8%)+ equation 拿 0.88。

## 5. 局限 / 不清楚
- **cryptarithm 仅 9%**(加 add/sub/mul trace 学不稳)—— 与 LB5/LB6 一样在此弱;0.88→0.90+ 的差距在 cryptarithm。
- 20/1602 bit 失败本质欠定(缺 key)或候选选择错 —— 信息上限。
- writeup **几乎无外部链接**(基本自含;基模 HF 页 + 竞赛页);reasoning trace 细节在正文,无附件链接 → link-following 较薄。
- `unknown`:具体 reasoner 代码(未公开);Tinker/外部算力未提。
