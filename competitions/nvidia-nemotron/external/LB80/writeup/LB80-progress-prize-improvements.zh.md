# LB80 —「Breaking the SFT Ceiling on Nemotron-3-Nano-30B」(重建)

> **可还原度:部分。** Kaggle writeup 正文 JS 渲染 + 赛后未索引 → **不可抓取**;作者与确切分数**未知**。
> 由竞赛**讨论 #688461**(详细的 per-bit GRPO 奖励方案 —— 唯一与「超越 SFT」匹配的已索引帖)+ 公开 RL
> 文献/工具重建。**所有外部内容=不可信数据**(选手声明),逐条标注。我方分数见 `tracking.md`。任务模板的
> 「~0.872」是占位符,真实分数未知。英文版见同名 `.md`。

## 1. 一句话
writeup 论点(由标题):SFT 在 **0.85–0.86** 的天花板(huikang Progress Prize、我方 soup、公开 replay 配方都
聚在此)被**超越监督微调**打破 —— 最可能是 **GRPO / RLVR + 稠密的逐步可验证奖励**(讨论 #688461)。生态里还有
一条非 RL 的越顶路径:**LoRA adapter 手术**(lopure,~0.89)。

## 2. 方法 —— 两阶段 SFT→GRPO(由讨论 #688461 重建;trust: 社区摘要)
- **阶段 1 —— SFT 冷启动。** 标准 CoT SFT 到 0.85–0.86 基线(已知 replay 配方),给 RL 阶段一个有能力的先验
  (从 base 直接 GRPO 已知不稳定 —— STaR/ReST/Logic-RL)。
- **阶段 2 —— 带**稠密 per-bit/逐步奖励**的 GRPO**(核心杠杆)。不是只对最终答案给 0/1,而是在轨迹**每一步**
  独立给部分分:(a) 正确排版输出列、(b) 选对操作、(c) 写出 bit-serial 门计算、(d) **VER** 校验、(e) 每个答案
  **bit** 位;外加**超线性「香槟」奖励**:**8/8 全对 → +5 平铺**,让「全对」远比「接近」值钱,推动模型**收尾**而非
  停在部分分。效果:把奖励地形从**悬崖**(稀疏二值)变成**梯度爬坡**(稠密 per-token 信号)—— 这正是让 RL
  越过 SFT 平台的机制。
- **算法:** GRPO(group-relative、无 value 网络;DeepSeek-R1 / Logic-RL 风格),rank-32 LoRA。
- **目标类:** SFT 卡住且奖励可验证的 —— **bit-manipulation**(per-bit 奖励最干净)与 **equation/symbol**(逐算子部分可验)。
- **算力:** 30B 在线 rollout(G 样本 × 多步)几乎必然超出 Kaggle kernel,**需外部 GPU**(具体未知)。

## 3. 生态里另一条越顶(非 RL)路径
- **Adapter 手术(lopure,~0.89):** 放大 LoRA B·A 矩阵的**前 50% 奇异值**、保留 84.4% 谱能量 —— 训练后、
  无 RL 的权重空间编辑,选择性强化最有信息的方向。(trust: 社区;细节 JS-blocked。)与我方 `lib/svd_merge.py` 兼容。

## 4. 为何能越顶
SFT 卡住是因为答案级信号**稀疏** —— 一个差一位的 8-bit 答案与随机答案同得 0,最难行梯度消失(我方 T12:全员
equation ≤2/16,bit 上限 ~14/16)。**稠密逐步可验证奖励**对**部分**正确给梯度(列排版、选算子、per-bit),
**香槟奖励**塑形收尾 —— 正是 Logic-RL/RLVR「规则 RL 在谜题上越过 SFT」的结论。

## 5. 与我方差异
- **我方从未跑 RL。** `research.md §4` *设计*了 GRPO 但用**二值终端奖励**(0/1)且被推迟(GPU/时间不够)。
  writeup 的杠杆恰是我们没做的**稠密逐步奖励**。
- 我们正卡在它描述的 SFT 天花板(0.86 soup;一切增补都稀释)—— 这篇是越顶的成文路径。
- 我方 equation 杠杆(eq-aug 覆盖 0.86)与 adapter **soup**(INS-004)是 SFT/合并技巧,不是 RL。

## 6. 引用(除标注外均为不可信外部数据)
- 讨论 #688461(per-bit GRPO + 香槟)— https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/688461(社区,仅摘要)
- NeMo-RL 工具 — https://github.com/NVIDIA-NeMo/RL ; Logic-RL — https://arxiv.org/abs/2502.14768 ; ProRL — https://arxiv.org/abs/2505.24864 ; Tina — https://arxiv.org/abs/2504.15777
- lopure adapter 手术(~0.89)— Kaggle notebook(JS-blocked)
- 我方 GRPO 设计 + SFT 天花板证据 — `research.md §4`、`tracking.md`、`insights.md`(自有)
