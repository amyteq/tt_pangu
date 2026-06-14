# Tracking (中文存档 / zh sidecar)

> 本文件**逐字保留** GitHub issue #86 正文(中文三表 + 快照 + 赛制 + 协作机制 + 合规红线)的快照,
> 仅供历史保存。英文规范版见 [`tracking.md`](./tracking.md);实时讨论见 issue #86(保持开放)。
> 快照来源:issue #86 body,导出于 2026-06-14。

---

# Nemotron Model Reasoning Challenge — 策略与追踪 Hub(中文版)

> 在此 issue 持续讨论、提问、推进 nemo 项目。详细分析见 📚 References 表中的文档;本正文只保留**三张工作表**,由 Claude **inplace 更新**(见底部协作机制)。
>
> **快照** *(最后更新: 2026-06-14 ~05:00 UTC;**最好仍是 0.85 (v14 replay)**;两次冲 0.85+ 均未果:T7 merge=0.82、T11 v15 合成=0.84;建议守 0.85 收官)*:榜首 ~0.89 | base ~0.47 | 我们最好 **0.85 (v14 replay)** | 截止 **2026-06-15 23:59 UTC** | 提交 per-team 5 次/天

## 赛制一句话
提交 **rank≤32 LoRA adapter**(基模型 Nemotron-3-Nano-30B-A3B,Mamba+MoE)→ 评测端 greedy 解码(`max_tokens=7680, temp=0`)→ 提取 `\boxed{}` 比对(精确匹配或数值 1e-2),指标 accuracy。9 类推理题,train 9500 行,真实测试集隐藏。

---

## 🔓 表1 — Open Discussions(等 Harry 确认 → unblock)

| # | 议题 | 背景 | 等待确认 | 状态 |
|---|------|------|----------|------|
| D1 | B 方向 (firefly2006) 完成后的**提交**授权 | push 已获授权;提交是同账号同流程的下一步 | 「B 完成后由 Claude 直接以 firefly2006 提交」是否 OK? | ✅ 已确认 (2026-06-12) |
| D2 | v11 rejection-sampling 自蒸馏的 GPU 预算 | 需先用 base 模型批量采样生成 CoT(约 2–3 个 GPU session),再训练 | 是否批准这笔配额投入? | ✅ 已确认 (2026-06-12) |
| D3 | SVD merge (v13) 的范围 | ChatGPT v3 支持掺入 public adapter;我建议**只 merge 我们自己训练的** adapter,避免 repack 争议 | 同意仅限自有 adapter? | ✅ 已确认 (2026-06-12) |
| D4 | v12 Unsloth 路线优先级 | 离线 wheels(mayukh18/nemotron-packages)→ seq8192 + 更多步数,最接近公开 0.85 配方,但环境搭建有风险 | 优先级:高/中/低? | ✅ 已确认 (2026-06-12) |
| D5 | 外部 GPU 资源选型 | #83(lightning.ai / Modal / RunPod / 本地 4090×不适合 30B) | 在 #83 给决策 | ✅ 已确认 (2026-06-12) |
| D6 | #85 YAML + user-pool 开工时机 | 设计已就绪;比赛只剩 ~4 天,工具化 vs 冲分的取舍 | 赛后再做,还是现在做? | ✅ 已确认:**赛后再做**(冲分优先) |
| D7 | inline 更新机制 | 我将直接**编辑你的 comment**逐条内嵌答复(引用+✅/💬),并 inplace 更新本正文三表;不新建 comment(避免触发 claude.yml、减少噪音);重大结果(分数/阻塞)仍发独立 comment | 这个方式 OK? | ✅ 已确认 (2026-06-12) |
| D8 | T10 复刻公开 0.86/0.87 配方要用 4 个第三方公开 Kaggle 数据集 | huikang 仓库快照(语料+训练顺序)+ mohamedamr992/replay-math + mayukh18/nemotron-packages + llkh0a/rtx-wheels;全部公开、自己**真实训练** fresh LoRA(非 repack,合规);本质是 T6/D4 的升级版,但数据源变了所以再确认一次 | 同意采用这些第三方公开数据集? | ✅ 已确认 (2026-06-12) |
| D9 | A/B 跑完后的 GPU 分配 | 建议:**A 账号跑 T10(公开 0.87 配方复刻,期望值最高)**,B 账号跑 T4 v10(自有 rule-CoT 路线,差异化+可进 T7 merge 池);T5 v11 排其后 | 这个分配 OK?还是先 v10? | ✅ 已确认 (2026-06-12);另:seq8192 继续,**全程 ≤8h 防超时** |

## 📋 表2 — TODO / 方向(Claude 推进,Harry comment 反馈)

| ID | 方向 | 说明 | 状态 |
|----|------|------|------|
| T1 | **A: nemo-cot-ctx4k** (harrysun2006) | masked CoT,seq4096,580 步(5.5h 截停),loss 0.147 → **LB 0.67,新最好** | ✅ 0.67 |
| T2 | **B: nemo-cot-ctx2k** (firefly2006) | 同语料 seq2048,583 步,loss 0.186 → **LB 0.42(低于 base)**;根因:右截断砍掉了序列末尾的 `</think>\n\boxed{}` 监督信号,模型学会「只思考不收尾」;教训:截断上限必须覆盖语料长度(seq8192 方向 ✓) | ✅ 0.42(负样本教训) |
| T3 | 今日 5 次提交额度利用 | A、B 各已提交(**2/5 已用**);A=0.67 为 per-day 最优,余 3 次建议留给 v10 结果 | 🟢 进行中 |
| T4 | v10: rule-aware CoT 数据 | [`firefly2006/nemo-rule4k-v10`](https://www.kaggle.com/code/firefly2006/nemo-rule4k-v10) v1:8000 例(4000 规则轨迹 + 4000 长 CoT),558 步,loss 0.93,held-out 3/4 → **LB 0.59**。高于 base(0.47)但低于 0.67:短规则轨迹替换一半长 CoT 让 greedy 推理变浅;**结论:数据优先长 CoT,规则信号应做成「带完整中间步骤的长轨迹」(=T11 v15 的做法),adapter 留作 T7 merge 池成员** | ✅ 0.59(进 merge 池)|
| T5 | v11: rejection-sampling 自蒸馏 | base 采样→只留答对的 CoT→SFT | 📝 计划中(D2 ✅,排队等 GPU session) |
| T6 | v12: Unsloth ~1 epoch / seq8192 | 公开 0.85 配方复刻 | 📝 计划中(D4 ✅,A/B 之后) |
| T7 | **多 adapter SVD merge** | [`harrysun2006/nemo-merge-t7`](https://www.kaggle.com/code/harrysun2006/nemo-merge-t7):三个 adapter 结构对齐(v10/ctx4k 是 v14 的子集,仅 Mamba in/out_proj + MoE experts/shared_experts;v14 另含 attention + lm_head)。对 **5980 个共享模块**做 `SVD_rank32(1.0·v14 + 0.25·ctx4k + 0.25·v10)`(v14 满权+有界微调,QR trick 免实体化 [out,in]);v14 独有的 25 个 base(attention+lm_head)原样保留;config 抄 v14 → 与 0.85 adapter 结构完全一致必可加载。本地校验:ΔW reldiff vs v14 ≈0.18–0.27、lm_head 逐字节相同、rank32、全 finite → **LB 0.82,低于 v14 的 0.85(−0.03,回归)**。**结论**:弱 adapter(0.59/0.67)即便仅 0.25 权重,叠加 + rank-32 截断也稀释了 v14 的共享模块 delta;weight-space merge 只在「多个分数相当、互补」的 adapter 间有效,strong+weak 不行。merge 路线到此为止,**最好仍是 0.85**(LB 取最大,无损失)。源码已并入 main(#94)| ✅ 0.82(负结果,merge 路线关闭)|
| T8 | 时间预算机制(v9 超时根治) | TrainerCallback wall-clock 截停 + 8 条限时 eval + save/zip 必达 | ✅ done(已进 A/B) |
| T9 | per-comp YAML + user-pool 工具化 | #85 | 🗓 赛后(D6 ✅) |
| T10 | **v14: 公开 0.86/0.87 replay 配方复刻**(T6 升级版) | [`harrysun2006/nemo-replay-v14`](https://www.kaggle.com/code/harrysun2006/nemo-replay-v14):配方 = huikang token 语料(录制顺序)+ replay-math 2M answer tokens,seq8192 / ≤1000 步 / LR 3.5e-4 / **CCE + MoE 128 专家 tying + lm_head/in_proj/out_proj target** + 7h 训练 deadline。**v1 几分钟即 fail-fast**:公开「0.87 复刻」notebook 的 replay 加载在现 Kaggle 镜像下 `apply_chat_template(tokenize=True)` 返回 BatchEncoding → len 比较变成字典键数比较 → 0 条样本(说明该公开 notebook 可能从未真正跑通);已修(解包 input_ids + 首行诊断),v2 跑通:**254/254 步**(8153 例 ÷ batch32 的 floor 上限,即 1 epoch;1000 步本来就会被 clamp)、replay 323 例 / 2.0M answer tokens / skipped=0、LR 完整衰减、final loss ~0.05、submission.zip 校验通过(rank32/α32) → **LB 0.85,新最好(0.67→0.85,+0.18)**!公开 replay 配方成功复刻,逼近榜首 0.89。源码已并入 main(#90) | ✅ **0.85** |
| T11 | **v15: cryptarithm 合成数据 + v14 骨架** | [`harrysun2006/nemo-synth-v15`](https://www.kaggle.com/code/harrysun2006/nemo-synth-v15) **运行中**(PR #95)。生成器 `kernels/synth/nemo_synth_gen.py`(改编自 varianceofx):**2640 例,cryptarithm 占 60%**(deduce 900 + guess 700),CoT 全部预计算中间值、结尾 finality 行、cryptarithm 查询掺未见符号;本地校验 exact CoT-answer 一致 **1930/1930**。集成方式:**v14 配方逐字不变**(CCE/MoE tying/seq8192/LR 3.5e-4/7h deadline),生成器内嵌,合成例按 replay 的 masking(reasoning_content + boxed,user 带 eval SUFFIX)在 kernel 内 tokenize 后交织进 Huikang+replay(每~3 例插 1 合成,占~24%);**无需新数据集**。运行干净:synth 全 2640 例 skipped=0、337/337 步、final loss ~0.002 → **LB 0.84,低于 v14 的 0.85(−0.01)**。**结论**:cryptarithm 合成数据没拉升;论坛早有迹象(「cryptarithm 8%→71% 但总分卡 0.86」),且 24% 合成占比可能轻微稀释其他类别。源码已并入 main(#95)。**v14 的 0.85 仍是最好** | ✅ 0.84(未超 v14)|
| T12 | 官方 metric 本地化 + min-logprob 难题验证集 | **完成计划**:① 把 lopure notebook 内嵌的官方 `score()`/`extract_final_answer()`/`verify()` 移植到 `kernels/eval/official_metric.py`(纯函数,本地可单测);② 难题验证集**不用自己跑 GPU**:lopure notebook 已附每类 min-logprob 最难题 ID 列表(~150 题),直接抄成 `eval/hard_val_ids.json`;③ kernel 的 held-out eval 换成从 hard_val_ids 抽样 + 官方 extract/verify(替代现在的字符串全等);随 v15 kernel 生效 | 📝 随 v15 |
| T13 | **修复 held-out eval 截断 bug** | `EVAL_MAX_NEW` 512→**7680**(对齐官方),外加 **EVAL_TIME_CAP=1800s** 整体 wall-clock 上限(超时报 partial n,不再威胁 session 预算);已进 v10 kernel,后续 kernel 继承 | ✅ done(已进 v10)|

## 📚 表3 — References

| 文档 | 位置 | 说明 |
|------|------|------|
| ChatGPT 比赛分析 (Q&A) | [`temp/nemo-chatgpt-analysis.md`](https://github.com/amyteq/tt_pangu/blob/dev/temp/temp/nemo-chatgpt-analysis.md) | 官方评测参数、test.csv=train 前 3 行、tinker repack 判定、讨论区方向 |
| ChatGPT v1 脚本 | [`temp/nemotron_v1_answer_only_sft.py`](https://github.com/amyteq/tt_pangu/blob/dev/temp/temp/nemotron_v1_answer_only_sft.py) | answer-only SFT baseline(≈我们 v5) |
| ChatGPT v2 脚本 | [`temp/nemotron_v2_cot_rule_augmented_sft.py`](https://github.com/amyteq/tt_pangu/blob/dev/temp/temp/nemotron_v2_cot_rule_augmented_sft.py) | 按 6 类题型生成确定性规则 CoT(T4 的核心输入) |
| ChatGPT v3 脚本 | [`temp/nemotron_v3_merge_svd_submit.py`](https://github.com/amyteq/tt_pangu/blob/dev/temp/temp/nemotron_v3_merge_svd_submit.py) | adapter 加权合并 + SVD 压 rank≤32 + 干净打包(T7) |
| Claude 中文分析 | [`temp/nemotron-analysis-claude.md`](https://github.com/amyteq/tt_pangu/blob/dev/temp/temp/nemotron-analysis-claude.md) | 赛制/挑战/提分技术/时间控制/成绩轨迹/合规 |
| Kernel README(成绩轨迹+坑) | [`kernels/kernel/README.md`](https://github.com/amyteq/tt_pangu/blob/main/kernels/nvidia-nemotron-model-reasoning-challenge/kernel/README.md) | 0.47→0.61→0.65 进展、ptxas 等 gotchas、三层防错 |
| Kaggle kernel 运维手册 | [`docs/tooling/kaggle-kernel-ops.md`](https://github.com/amyteq/tt_pangu/blob/main/docs/tooling/kaggle-kernel-ops.md) | 版本模型(latest-only)、flat 结构、并发/配额 |
| 比赛主页 | [Kaggle](https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge) | Overview / Data / Code / Discussion |
| 工具链 PR(已合并) | #81 · #82 · #84 · #75 | #81 `kca kaggle submit --kernel/--version`(本赛的提交通道:直接提交 Kaggle storage 中的 kernel output);#82 push 前静态 lint gate(v9 NameError 教训;nemo kernel 源码也随此 PR 入库);#84 kernel/version 模型 + flat 结构 + 并发手册;#75 `/kaggle/input/competitions/<slug>` 新挂载路径 |
| 实验 kernel PR(已合并) | **#90** | v10 (`nemo-rule4k-v10`) + v14 (`nemo-replay-v14`) kernel 源码 + flat metadata,均含 ≤8h wall-clock 守护;附带 CI/本地 ruff 钉到 0.15.14(根治 format gate 漂移)。源码:`kernels/kernels/{nemo-rule4k-v10,nemo-replay-v14}/` |
| 决策类 issue(开放) | #83 · #85 · #21 | #83 外部 GPU 算力选型(= 表1 D5);#85 per-comp YAML + user-pool 设计(= D6/T9,赛后做);#21 多账号提交配额池(#85 的前身,双账号策略的早期讨论) |
| 已知坑 issue(开放) | #77 · #78 | #77 kernel push ≠ leaderboard 提交,goal loop 需显式 submit 步骤;#78 `kca competition refresh-rules` 在 kaggle 2.0.x 上失效 |
| 姊妹追踪 hub | #87 | Orbit Wars 长期追踪与策略讨论(同款三表 + inline 更新协作机制) |
| 公开 0.87 配方 notebook | [kuangyicheng/nemotron-087-training](https://www.kaggle.com/code/kuangyicheng/nemotron-087-training) | T10 的来源:0.86 replay 配方的干净复刻(CCE + MoE tying + lm_head LoRA + seq8192),声称 0.87 |
| huikang 开源仓库 + 可视化 | [tonghuikang/nemotron](https://github.com/tonghuikang/nemotron) · [nemotron.huikang.dev](https://nemotron.huikang.dev) | Progress Prize 得主全 pipeline(solver 调查→合成→语料→SFT);base 模型逐题表现 / 逐题规则调查状态可视化,选难题验证集直接可用 |
| lopure adapter 手术 notebook | [amplify-top-50-singular-value](https://www.kaggle.com/code/lopure/amplify-top-50-singular-value-retain-84-4-energy) | 榜首区(0.89)选手:adapter 后处理(gate/x_proj 共享基 SVD 合并、奇异值放大)、内嵌官方 metric 代码、min-logprob 难题集(T12 来源) |
| 合成数据生成器(49k) | [varianceofx/synthetic-dataset-generator-27k](https://www.kaggle.com/code/varianceofx/synthetic-dataset-generator-27k) | 10 类题型确定性生成器+CoT;防自我推翻 finality 行、未见符号泛化训练(T11 参考) |

> 临时文档统一放 **`dev/temp` 分支 `temp/` 目录**(`test.yml` CI 只在 push:main/PR 触发,本分支推送**不跑 CI**,push 很快)。

---

## 🤝 协作机制(D7 待确认)
1. **本正文三表由 Claude inplace 更新**(`gh issue edit`),每次更新刷新顶部「最后更新」时间戳。
2. **你的 comment**:Claude 直接编辑该 comment,在每条下内嵌答复(`> 引用` + ✅完成/💬讨论/🔒阻塞),不新建 comment。
3. **重大事件**(LB 分数、超时/失败、需要决策)Claude 发独立 comment @ 提醒。
4. 你在表1勾选/答复 → unblock 对应 T 项;在表2行内 comment → Claude 继续推进。

## 合规红线
rank≤32;真实训练(不 repack);双账号 = 真实注册队友(已确认),只买**并发 session**,提交共享 per-team/day;不打印/提交 credentials。















