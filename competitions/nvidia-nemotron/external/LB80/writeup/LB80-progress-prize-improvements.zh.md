# LB80 —「Breaking the SFT Ceiling on Nemotron-3-Nano-30B」(直接据 writeup)

> **来源:** Kaggle writeup,作者 **Mayur Pawar**(`mspawar`),**直接读自 `temp/LB80.pdf`**(15 节全文渲染)。
> **可还原度:完整** —— 取代此前 JS-blocked 重建(那版据竞赛讨论 #688461 误把**另一个人**的「per-bit GRPO +
> 香槟奖励」当成本文,实际**不是** mspawar 的 writeup)。外部内容=不可信数据(选手声明),逐条标注;我方分数见
> `tracking.md`。配套 notebook:`kaggle.com/code/mspawar/breaking-the-sft-ceiling-on-nemotron-3-nano-30b`;
> 数据集:`kaggle.com/datasets/mspawar/nemotron-cot-training-data-v2v12v13`。英文版见同名 `.md`。

## 0. 一句话(标题是诚实而非凯旋)
最终**私榜 0.86,排名 80/4190(top 1.91%)**。本文是 **30+ 实验的系统研究,证明了 SFT 天花板 = 0.86** ——
STaR、GRPO、DPO、权重平均**全都没能突破**。名次提升(「相对未对冲的 V2×2 反事实 +397 名」)**不是来自更高分**,
而是来自在**公私榜双峰失配**下的**结构性提交对冲**。0.86 基线本身(V2,4/21)**直接建立在 Tong Hui Kang 的**
确定性 solver 方法上(与 LB25 同源),且自始至终没被超过。

## 1. 真正有效的杠杆(SFT)
- **序列长度 4096→8192 = 最大单跳(0.46→0.77,V21)。** seq 4096 时 **43% 训练数据被静默丢弃**(completion 超长),
  最伤最难类(其 CoT 最长)。截断是隐形数据质量杀手 —— 被截行仍贡献 loss,却教会「只推理不收尾」。*(对应我方
  ctx2k 0.42 / ctx4k 0.67 → v14 seq8192 0.85。)*
- **全线性 LoRA target(V8e,突破):** 对*每个*线性层(含 `lm_head`)加 LoRA > 选择性。*(= 我方 v14。)*
  **排除 `gate_proj`**(MoE 路由器),否则「专家坍塌」。
- **确定性 solver CoT ≫ 模型生成 CoT**(其核心原则,= huikang):模型自 CoT 回归(V7 0.60);外部长 CoT
  (DeepSeek-R1,V10b)**灾难性 → 0.27**(比不加 adapter 还差)。「训练数据的质量上限由 solver 决定,不是模型。」
  *(= 我方 INS-006 + andy279 0.81 回归。)*
- **黄金超参(V2,0.86):** LR 2e-4、2 epoch、batch 64、seq 8192、rank 32/alpha 32、dropout 0、线性衰减、warmup 0、
  AdamW β2 0.95、grad-clip 关。*(基本就是我方 v14 配方。)*

## 2. equation/cryptarithm 的结构 —— 而且离线**可破**(对我方关键)
**这修正了我方 EQ-0/EQ-2′ 的框定。** mspawar 对我们称为 `equation` 类的分析:
- **输入 = 5 字符 `A1 A2 OP B1 B2`** = **两个 2 字符操作数 + 一个 1 字符运算符**,符号集
  `!@#$%^&*()_+-=[]{}|;:'",.<>?/\~`。输出 1–4 字符同集。**每题有自己的符号→数字双射**(逐题密码),3–5 个示例方程 + 1 查询。
  子类:`cryptarithm_deduce`(运算符出现在示例)/ `cryptarithm_guess`(没出现)。
- **离线破解 97.6%**(569/583),用**答案引导的排列搜索**(V3,「83 种操作」):*对每个数字符号排列 → 0-9:先解码
  真值答案,找出能产出它的操作,再核验所有示例方程。* 答案优先剪枝砍掉 ~99% 的 `83 ops × 10! × 4 反转模式` 空间。
  14 个不可解的有 **11+ 个不同数字符号**(10 个数字装不下)。`equation_symbolic` 用 CP-SAT 达 **87.5%**(720/823)。

> ⚠️ **这与我方 EQ-0「单一全局函数」模型、EQ-2′「不可破强密码」结论矛盾。** 我们找的是 5 字符→1-4 字符映射的
> 一个全局 σ;mspawar 表明它是**逐题**密码、结构为 `A op B`、运算符空间有限 —— 且**能**用答案离线破解。我方 EQ-2′
> 可能**解错了问题**。**强烈建议重审 EQ-0/EQ-2′**(见 `analysis/next_version_plan.md`、`analysis/gap_analysis.md`)。

## 3. 为何 97.6% 覆盖的 solver 仍没拉升 LB ——「发现泄漏(discovery leakage)」(最深的教训)
- 答案引导 solver 是**用答案**找映射,然后 CoT 把映射**「作为已知」直接给出**、不含发现搜索。于是模型学会**核验**
  一个映射、而非**发现**一个 —— 但推理时没有答案,需要的正是发现。→ 训练 1000+ 例后 cryptarithm 仍 **8.5%**。
- 更糟(全量审计):**93–97% 的 cryptarithm 轨迹是*内部不一致*的** —— 所述数字映射其实产不出 boxed 答案(solver 经
  CoT 没展示的搜索路径才到答案)。模型**记忆答案、非过程**。
- 在 `equation_numeric` 上的修复:把答案派生步骤换成**可由 prompt 前向推导**的策略 → 修了 **37 个系统性推理错误**。
  但展示完整约束搜索的前向 CoT 可能**超过 8192 token**;逐步推导 CoT 只得 **0.84**(无提升)。**榜首 0.90(rank 32)
  说明*存在*某种 CoT 形式能破 cryptarithm** —— 开放问题。

> **→ 这解释了我方 eq-aug(覆盖式记忆)为何封顶**:我们教模型复现见过的对(核验),而非跑逐题密码发现。真正的杠杆是
> **前向可执行**的密码发现 CoT(在长度允许下)。

## 4. SFT 为何封顶 + 标准 RL 为何在此失效(二值失败模式)
- **SFT 天花板 = 0.86,6 个独立实验证明**(更多数据、新类别、模型 CoT、超参、更多训练、类别侧重 —— 全部持平或回归 V2)。
  SFT 交叉熵只说「让这个输出更可能」,从不说「让那个错输出更不可能」→ 错推理路径仍高概率,且加类别稀释脆弱均衡。
- **二值失败现象:** temp 0.7、N=8 —— **3,157 难题 0/8、~6,343 易题 8/8、0 题落在 1–7/8**。没有「边界」题。
  - **STaR** 产出 = **0%**(难题没有对的可筛)。
  - **GRPO** 优势 = **0**(组内奖励无方差 → 零梯度)。「GRPO 需要一定密度的边界题才能工作。」*(这才是 RL 失败的真因 ——
    不是缺稠密 per-bit 奖励;我此前的重建是错的。)*

## 5. DPO 流水线(真正的「超越 SFT」尝试 —— 仍未破 0.86)
DPO 用**外部 oracle**(solver CoT)作 *chosen*、模型自身 *greedy 失败* 作 *rejected* 绕开二值墙 —— 不需边界题。设计:
- **双温度生成:** greedy `temp=0, N=1` 抓**确切评测时失败**作 rejected(评测用 greedy,即最高概率错输出)+ `temp=0.7, N=8` 求多样。
- **配对:** 离群 → chosen=solver CoT、rejected=greedy 错;边界 → chosen=模型最短正确(实际没有);内群跳过。~2000–2500 对。
- **loss:** 长度归一化 DPO margin + 在简单类(cipher/gravity/numeral/unit)**混 SFT** 防遗忘;**参考模型 = 同基座关掉 LoRA**(toggle,省 ~60GB)。
- **结果:** V12(审计修复数据)/ V13(V12 + 一致性重生)**停在 0.84–0.86** —— 即便数据完整性改善,SFT 天花板仍在。

## 6. Mamba-2 上权重平均失效(与我方 INS-004 的张力)
「**首个记录:Model Soup 在混合 SSM 架构上失效。**」Mamba-2 的 SSM 参数(A、B、C、D 递推矩阵)编码**时间动态**;
跨 checkpoint 朴素平均会破坏它们。*(V9 merge V8d+V8e 仅在更低分上有微弱增益。)*

> ⚠️ **与我方 INS-004 张力**(我们靠 v14+c1+b1 的 SVD 模型汤 **0.85→0.86**)。调和假设(待验证):(a) 我方汤平均的是
> **冻结基座上的 LoRA *delta*** + **SVD rank-cap**,而非完整 SSM 递推矩阵,SSM 动态扰动更小;(b) 是同 basin、低权重
> (0.4/0.3/0.3)、*分数相当*成员的合并,增益很小(+0.01,在 ±0.04 评测方差内)。我方的汤可能是比他发现有毒的全权重
> 平均**更窄更温和**的操作 —— **值得做一次 SSM-vs-LoRA-delta 合并消融**,别过度相信任一说法。

## 7. 名次提升 = 选择对冲,非分数跳升
最终选:**V2 原版(主)+ V8 ckpt-400(结构对冲)**。在**公榜(n≈250)不预测私榜**的**双峰失配**下,对冲扛住了私榜抽样,
相对同作者**未对冲 V2×2** 反事实 **+112 名 / +397 名**。*(强选择纪律证据 —— = 我方 INS-005/INS-007 与 LB25「0.872 占
4/15 / 本可单人金牌」。)*

## 8. 基础设施 / 流程(简)
最低可用 GPU = **95.6 GB 显存、sm_90+**(RTX PRO 6000 Blackwell / H200);Kaggle T4×2、Colab A100-40GB **均失败**(7 种
失败 / OOM)。~**335 GPU 小时、~$2,000**(Vast.ai + Colab Pro+;GCP 配额被拒)。vLLM 生成与 HF 训练用**独立进程**(不共享
显存)才能把 N=8×7680 塞进 95.6GB。Notebook 用 **Claude Code** 编写/调试。

## 9. 引用
- **writeup(全文):`temp/LB80.pdf`**(Kaggle writeup 渲染;以上各节一手来源)。
- 配套 notebook / 数据集(Kaggle,JS 锁)— `mspawar/breaking-the-sft-ceiling-on-nemotron-3-nano-30b`、`mspawar/nemotron-cot-training-data-v2v12v13`。
- 建立在 `tonghuikang/nemotron`(确定性 solver 方法);NVIDIA Nemotron-3-Nano 报告 arXiv 2512.20848。
- 我方分数/配方 + EQ-0/EQ-2′ — `tracking.md`、`submissions.md`、`equation-frontier.md §8`、`insights.md`(自有)。
