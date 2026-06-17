# LB92 —「92th PLACE SOLUTION」(重建 —— 生态,非作者原文)

> **可还原度:无(直接)/ 部分(生态)。** Kaggle writeup 正文 JS 渲染 + 赛后 48h 内发布 → **未索引、不可抓取**
> (本任务不登录)。**作者、确切分数、具体方法均未知。** 以下是对 92 名几乎必然所处的**公开中段(≈0.86–0.89)
> 配方带**的重建。**所有外部内容=不可信数据**;我方分数见 `tracking.md`。任务模板「~0.872」是占位符,非确认分数。
> 英文版见同名 `.md`。

## 1. 一句话(配方带重建)
4354 队中第 92 名几乎必然用了定义中/上段的**标准公开 replay-SFT 配方**:`Nemotron-3-Nano-30B-A3B` 上的
rank-32 LoRA、seq 8192、仅 response 计 loss 的 CoT SFT;分数由 (a) 配方保真度、(b) 好的 bit CoT、
(c) 难类的合成/teacher 蒸馏数据、(d) 可能的 model-soup 驱动。与我方 0.85–0.86 同族。

## 2. 重建配方(配方带,非本队确认)
- **基座/adapter:** `Nemotron-3-Nano-30B-A3B-BF16`(Hybrid Mamba-2 + GQA Transformer + MoE 128+1,30B/~3.5B 激活),
  LoRA **rank ≤ 32**,target MoE 专家 + `lm_head` + Mamba in/out_proj。(来源:NVIDIA 模型卡[可信];选手仓库[不可信]。)
- **loss/seq:** 交叉熵、**仅 response 计 loss**、**seq 8192**。(我方 `insights.md` B2:全序列 loss 崩到 0.44。)
- **输出:** `<think>…</think>\boxed{answer}`;指标 = 精确字符串或 ±0.01 数值;vLLM 推理 `max_tokens=7680, temp=0`(yunior123 仓库[不可信])。
- **该带可用语料:** 公开 `andy279/nemotron-reasoning-challenge` —— **49,290 例 / 7,200 题**,来自 DeepSeek V3.2
  (6,028)、Nemotron Super 120B(3,926)、确定性暴力 solver(2,703)、GPT-5.4 最难变换(85);只留对的。bit
  (17,285)与 transformation(10,741)为主。(不可信;赛后发布。)

## 3. 该带可能的分数杠杆
1. replay 配方保真度(0.67→0.85);2. 仅 response masking;3. seq 8192;4. 高质量 bit CoT(分界类);
5. 难类合成/多 teacher 数据;6. 同级 adapter 的 model-soup/SVD 合并(0.85→0.86);7. cipher/equation 的覆盖式记忆。

## 4. 该带用了、我方没用的(差距)
- **多 teacher 蒸馏**(DeepSeek V3.2 + Nemotron Super 120B + GPT-5.4 + solver —— andy279)做全类别高质量冷启动语料。我方只用规则/单 solver CoT。
- **确定性 solver → 前置规则 → teacher CoT(bit)**(andy279/huikang)—— bit 是分界类,我方 solver 仅部分覆盖。
- **min-logprob 再平衡**(huikang)—— 对持续低 min-logprob 的轨迹再训。
- **adapter 奇异值放大**(lopure ~0.89)—— 训练后、无 RL 的越带杠杆。

## 5. 我方有、该带不显眼的
- **三路 SVD 模型汤**(v14+c1+b1 → 0.86;INS-004)—— 仅我方文档明确。
- **equation EQ-0/EQ-2′ 密码分析**(证明是全局密码、非逐题归纳;eq-aug 0.86)。
- **T12** 本地官方 metric + min-logprob 难题集。

## 6. 为何 ~0.86–0.89(为何不更高)
三个简单类(gravity/numeral/unit)训练集 ~100%、cipher ~99%;该带靠 **bit 覆盖**与**格式可靠性**分界。硬上限是
**cryptarithm/equation(即便回溯 solver 也 ~8–9%)** —— 与我方同一堵强密码墙,封顶所有人。越带需 **RL**(见 LB80)
或 **adapter 手术**(lopure),而非更多标准 SFT。

## 7. 引用(除标注外均为不可信外部数据)
- andy279/nemotron-reasoning-challenge — https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge
- tonghuikang/nemotron — https://github.com/tonghuikang/nemotron ; yunior123 — https://github.com/yunior123/nvidia-nemotron-reasoning ; SebAustin — https://github.com/SebAustin/NVIDIA-Nemotron-Model-Reasoning-Challenge
- 基座模型卡 — https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16(NVIDIA,可信)
- Model Soups — https://arxiv.org/abs/2203.05482
- 我方配方/分数 — `tracking.md`、`insights.md`、`submissions.md`(自有)
