# NVIDIA Nemotron Model Reasoning Challenge — Claude 分析与计划

> 状态快照(2026-06-12):榜首 ~0.88–0.89;base(未训练 adapter)~0.47–0.50;
> 我们最好成绩 **0.65**(v7, masked CoT);截止 **2026-06-15 23:59 UTC**;
> ~4170 队;$106k。追踪 hub:issue #86。

## 一、比赛是什么

- **任务**:推理谜题 `prompt` → 模型输出答案,最终答案放进 `\boxed{}`。
  评测提取 `\boxed{}`(回退启发式/最后一个数字)比对,指标 **accuracy**。
  判对标准:**字符串精确匹配 或 数值相对误差 ≤ 1e-2**。
- **官方评测推理参数**(来自 ChatGPT research):`max_tokens=7680`、
  `temperature=0.0`(greedy)、`top_p=1.0`、`max_num_seqs=64`。
  ⇒ 长 CoT 预算充足;**greedy 解码 ⇒ 评测端没有 self-consistency 投票空间**,
  功夫只能下在训练;adapter 必须**稳定收尾 `\boxed{}`**。
- **数据**:`train.csv` 9500 行(`id,prompt,answer`);public `test.csv` 仅 3 行
  (即 train 前 3 行,sanity 用,真实测试集隐藏)。9 类题型:
  bit_manipulation / cipher / cryptarithm_(deduce|guess) / unit_conversion /
  gravity / numeral / equation_numeric_(deduce|guess)。
- **提交物**:**rank ≤ 32 的 LoRA adapter**(基模型固定
  Nemotron-3-Nano-30B-A3B,混合 Mamba + MoE,30B 总参 / ~3B 激活),
  `submission.zip` 根目录直接含 `adapter_config.json` +
  `adapter_model.safetensors`(**不能多包一层目录**)。

## 二、我们的成绩轨迹(全部为真实训练,非 repack)

| ver | 改动 | LB |
|----|------|----|
| identity | 未训练 adapter(管线验证) | 0.47 |
| v5 | bare-answer SFT,120 步 | 0.61 |
| v6 | CoT 但 loss 算到 prompt+padding(bug) | 0.44 |
| **v7** | CoT + response-only masking,400 步 | **0.65** |
| v8 | + held-out eval | `.shape` 崩溃(BatchEncoding)→ 已修 |
| v9 | + 修复后 eval | **12h 超时**(64 条自回归生成 eval 太慢) |
| A: nemo-cot-ctx4k | 时间预算化,seq4096 | running |
| B: nemo-cot-ctx2k | 时间预算化,seq2048→更多步数(may 账号) | running |

## 三、主要挑战

1. **rank≤32 硬约束**:本质是"对齐/激发基模型已有推理能力 + 规范输出格式",
   不是灌新知识;提升上限受 LoRA 容量限制。
2. **30B Mamba-MoE 工程坑**(都踩过):
   - `ptxas-blackwell` 在只读挂载不可执行,且捆绑 Triton 无视
     `TRITON_PTXAS_PATH` → 复制到 `/tmp` + `chmod +x` +
     `TRITON_PTXAS_BLACKWELL_PATH` + monkeypatch `get_ptxas_version`;
   - MoE `lm_head` LoRA 兼容性(Tinker 转换讨论:提交时 drop `lm_head` /
     `modules_to_save`,fused expert 需拆分);
   - bf16 ~60GB 加载,只有 `NvidiaRtxPro6000`(96GB)跑得动。
3. **隐藏测试集**:public 3 行无信号 ⇒ 过拟合风险;9 类必须分层覆盖。
4. **CoT 长度 vs 收尾**:教了长推理后必须确保按时 `\boxed{}` 收尾。
5. **Kaggle 资源 = 迭代瓶颈**:每账号 ~1 并发 GPU session、~30h/周浮动配额、
   12h 单次硬限;提交 per-team/day。⇒ flat 多 kernel + 双账号(真实队友,
   #85)+ 时间预算化。
6. **一个 typo = 浪费一次 2h+ GPU run**(v7 `texts`、v8 `.shape`)⇒
   三层防护:静态 lint gate(#82)、fail-fast preflight、隔离 eval。

## 四、时间控制设计(v9 超时教训,已实装进 A/B)

- **训练 wall-clock 预算**:`TrainerCallback.on_step_end` 超过
  `TRAIN_BUDGET_SEC`(5.5h)即 `should_training_stop`;`max_steps` 只是次级上限。
- **小型限时 eval**:8 条 × `max_new_tokens=512`(原 64×1024 是超时元凶);
  运行超过 6.5h 则整体跳过 eval。
- **save+zip 永远可达**(快,且在 eval 隔离的 try 之外)。

## 五、提分技术(按杠杆排序)

1. ★★★ **CoT 推理轨迹 SFT**(已验证 0.61→0.65)。
2. ★★★ **Rejection sampling / STaR 自蒸馏**:用 base 对每题采样多条,
   只保留答对的 CoT 做训练数据 —— 贴合本模型分布且天然正确。
3. ★★★ **SFT 细节**:response-only masking;chat 模板 +
   `<think>…</think>\boxed{}`;EOS;~1 epoch(公开 0.85 ≈ 1000 步);
   LR 2e-4 cosine;`alpha=rank`。
4. ★★ **数据质量/覆盖**:9 类分层(dgxchen 用 stratified batching)、
   难度加权、去重、答案格式与评测提取严格一致。
5. ★★ **LoRA 配置**:rank 32 顶格;target 覆盖 attn/MLP/mamba 的
   in/out/up/down proj;MoE `lm_head` 谨慎处理。
6. ★★ **训练↔评测对齐**:简短推理 + 立即收尾,确保提取稳定。
7. ★ **Unsloth**(离线 wheels):省显存 → seq 8192 + 更多步数。
8. ★ **SVD adapter merge**(ChatGPT v3):多个**自己训练**的 adapter
   (不同 seed/LR/数据混合)加权合并 → SVD 压回 rank≤32。
   注意:只 merge 自有 adapter,不用 public repack。
9. 借鉴真实公开**训练** notebook(dgxchen Unsloth / huikang end-to-end /
   kienngx CoT),排除 tinker 纯打包。

❗ 不可行项:self-consistency 投票 —— 提交的是 adapter,解码由评测端决定
(greedy),test-time 技巧用不上,重心全在训练。

## 六、ChatGPT 三个脚本的定位(temp/ 同目录)

| 脚本 | 内容 | 用途 |
|------|------|------|
| `nemotron_v1_answer_only_sft.py` | answer-only SFT(≈我们 v5) | 稳健 baseline / 环境验证 |
| `nemotron_v2_cot_rule_augmented_sft.py` | 按 6 类题型生成确定性规则 CoT(无需外部 LLM)+ 保留 answer-only target | **最有希望的数据方向**(v10 候选) |
| `nemotron_v3_merge_svd_submit.py` | 多 adapter 加权合并 + SVD 压 rank≤32 + 干净打包(drop lm_head) | 后期集成(v13 候选) |

## 七、合规红线

rank ≤ 32;真实训练(不 repack 他人 adapter);双账号仅以**真实注册团队**
形式使用(may 已确认是真实队友);提交共享 per-team/day 限额(双账号买的是
**并发 session,不是提交次数**);不打印/提交 credentials;遵守竞赛规则。
