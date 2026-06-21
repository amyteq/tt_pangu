# Tracking (中文存档 / zh sidecar)

> 本文件**逐字保留** GitHub issue #86 正文(中文三表 + 快照 + 赛制 + 协作机制 + 合规红线)的快照,
> 仅供历史保存。英文规范版见 [`tracking.md`](./tracking.md);实时讨论见 issue #86(保持开放)。
> 快照来源:issue #86 body,导出于 2026-06-14。
>
> **⚠ 当前状态(2026-06-15,最新见 [`tracking.md`](./tracking.md)):** 自训练最好 = **0.86**
> (`nemo-merge-soup` = v14+c1+b1 的 SVD 模型汤,合规真训练)。冲刺最终分:b1 0.85 / b2 0.84 /
> c1 0.85 / c2 0.83 / **soup 0.86(新最好,打破 0.85 天花板)**。今日额度 5/5 用尽,0.86 锁定收官。
>
> **⚡ LB25/LB80/LB92 借鉴实验(2026-06-20,延迟提交窗口):** 跑了 v16-evalfix(LB25)、v17-discovery(LB80 A)、
> v18-stable(LB92)。**均未超过 0.86** —— v16 0.832/0.828(bit CoT + 重放稀释)、v17 0.840/0.848(equation 仍有界)、
> v18 0.844/0.848(grad-clip 1.5 ~持平)。三者都印证了各自计划里写明的「稀释 / equation 有界」风险;**soup/eq-aug 0.86 保持最好**。
> 两个与 LB 无关的真实收获:① **破解了 equation 密码** = per-operator 数字串规则;但团队的 `versions/lb1-v1/rules24.py`
> (deduce 95%,分支 `exp/nemo-postlb1-v1`)是更强的破解器,v17.1 应改用它;② **v17-dpo 推迟**(需外部 sm_90+ GPU,#83)。
> v18 的 LEVER 2 per-char 分词**判定不可行**(adapter-only 评测器用 base 分词器,新增 token 传不进去)而弃用。
>
> **T12 hard-val 排名(2026-06-15,`harrysun2006/nemo-t12-hardval` v2):** 移植官方 metric(greedy
> `max_tokens=7680, temp=0`,提取 `\boxed{}`/末尾数字,精确或数值 1e-2)+ min-logprob 每类最难题
> (难题 72 题:bit/equation/cipher 各 16,numeral/gravity/unit 各 8),对各候选 adapter 排名:
>
> | adapter | hard-val 准确率 | bit | equation | cipher | numeral/gravity/unit |
> |---|---:|---|---|---|---|
> | **soup** | **0.764** | 13/16 | 2/16 | 16/16 | 各 8/8 |
> | **v14** | **0.764** | 14/16 | 2/16 | 15/16 | 各 8/8 |
> | base(无 adapter) | 0.389 | 0/16 | 0/16 | 8/16 | 8 / 7 / 5 |
> | c1 | 0.389 | 1/16 | 0/16 | 3/16 | 各 8/8 |
> | v15 | 0.333 | 0/16 | 0/16 | 0/16 | 各 8/8 |
> | c2 | 0.278 | 1/16 | 0/16 | 2/16 | 7 / 3 / 7 |
>
> **结论:**(1)**0.86 soup 在难题上稳健、未被稀释**,与 v14 并列最高,难 cipher/bit 全拿;
> (2)**CoT/合成增补的 adapter(c1/c2/v15)在最难 cipher/bit 上跌到 base 同级甚至更低**(c1 cipher
> 3/16 < base 8/16,尽管它就是用 cipher CoT 训的)——base 基线排除了「没加载上」的假象:它们确实改变了
> 行为(简单类拉满 24/24)但**劣化了最难类**,印证「增补稀释干净 replay 配方」在难题切片上更明显;
> (3)**equation 全员未解(≤2/16)**,是唯一真正的前沿,cipher 类数据帮不上。
>
> **决策:守 0.86 soup 收官;cipher 重的 v11 stage-2 SFT 撤下**(a2 语料 94% 是 cipher → 同样的劣化风险)。
> **最终 private-LB 选择 = soup(0.86) + v14(0.85)**:v14 与 c1 公榜同为 0.85,但 hard-val 上 v14
> (0.764)远胜 c1(0.389),故 v14 是更稳的第二选择(soup 含 40% v14,二者相关,但 v14 系正是稳健的那支,
> 这种集中是有意为之)。
>
> 以下为 issue #86 于 2026-06-14 的**冻结**快照(其中「最好 0.85」为当时状态,勿据此更新)。

---

## T12 hard-val 逐版本 + EQ1..EQ4 分析(2026-06-16 赛后整理)

> 英文规范版见 [`tracking.md`](./tracking.md) 同名两节。T12 难题验证 harness(`nemo-t12-hardval`)**2026-06-15
> 才建好**,故只跑了**最终候选** adapter;更早的版本一律 **not run(未跑,非低分)**。hard-val 是**难尾代理**,
> 不是 LB——它会低估「只在最难切片上弱」的 adapter(eq-spec hard-val 0.167 vs LB 0.85)。以 **LB 聚合为准**,
> hard-val 仅作难尾提示(INS-002)。

| 版本 | 公榜 LB | 私榜 LB | T12 hard-val | 依据 |
|---|---:|---:|---|---|
| identity | 0.47 | 0.52 | not run | harness 晚于此版本 |
| v5 | 0.61 | 0.66 | not run | 同上 |
| v6 | 0.44 | 0.45 | not run | 同上 |
| v6′ | 0.47 | 0.46 | not run | 同上 |
| v7 | 0.65 | 0.66 | not run | 同上 |
| ctx4k (T1) | 0.67 | 0.66 | not run | 同上 |
| ctx2k (T2) | 0.42 | 0.46 | not run | 同上 |
| v10 (T4) | 0.59 | 0.64 | not run | 同上 |
| **v14 (T10)** | 0.85 | 0.84 | **0.764** | T12 v2(bit 14/16, eq 2/16, cipher 15/16, 其余各 8/8) |
| t7 merge | 0.82 | 0.80 | not run | 路线在 T12 建好前已关闭 |
| v15 (T11) | 0.84 | 0.84 | **0.333** | T12 v2(难 cipher/bit 跌到 ≤ base) |
| c1 | 0.85 | 0.85 | **0.389** | T12 v2(cipher 3/16 < base 8/16,增补稀释难尾) |
| c2 | 0.83 | 0.83 | **0.278** | T12 v2(难类加权 → hard-val 最差) |
| b1 | 0.85 | 0.84 | not run | 未进 T12 v2 排名 |
| b2 | 0.84 | **0.85** | not run | 未进 T12 v2(may 对冲,私榜 +0.01) |
| **soup** | **0.86** | 0.85 | **0.764** | T12 v2(与 v14 并列最高且稳健;**已选**) |
| surgery A | 0.86 | 0.84 | unknown | 某 surgery run 报告 hard-val 0.744 vs soup 0.731(**另一套**对比集),不在 T12 v2 规范排名内 |
| andy279 | 0.81 | 0.81 | not run | 外部 teacher CoT;LB 回归 |
| v11 自蒸馏 | 0.80 | 0.82 | not run | 拒绝采样 CoT;LB 回归 |
| base(无 adapter) | — | — | **0.389** | T12 v2 基线(bit 0/16, eq 0/16, cipher 8/16) |
| **EQ1 = eq-spec** | 0.85 | 0.85 | **0.167** | EQ §8.4(难尾不确定时答案抄近路;LB 0.85 ≫ hard-val——正是 INS-002) |
| **EQ2 = eq-aug** | **0.86** | **0.86** | **0.194** | EQ §8.4(自训练私榜最好;仍难尾弱 → 不可入汤) |
| **EQ3 = eq-hidose** | 0.84 | 0.84 | unknown | 未单独跑 hard-val |
| **EQ4 = eq-aug-hidose** | 0.85 | 0.82 | unknown | 未单独跑 hard-val |
| soup_v2(eq-aug 入汤) | 0.85 | 0.85 | unknown | SVD(0.86-soup×0.6 + eq-aug×0.4);稀释 < 两个父本 |
| **v16-evalfix**(LB25) | 0.832 | 0.828 | 未跑(本地无 GPU) | LB25 借鉴:eval/submission parity 预检(仅修测量)+ 验证过的 bit CoT 157 条 + min-logprob 选择性重放(最难 1198/37 步);**公 −0.018 / 私 −0.012 vs v14 → 稀释(印证计划首要风险)** |
| **v17-discovery**(LB80 A) | 0.840 | 0.848 | 未跑(本地无 GPU) | equation 发现式 CoT:破解了 per-operator 数字串规则族,180 条已验证明文数字样本(dose 0.15);82% 符号加密未破;**公 −0.01 / 私 +0.008 vs v14 → equation 仍有界(明文子集不迁移)** |
| **v18-stable**(LB92) | 0.844 | 0.848 | 未跑(本地无 GPU) | grad-clip 1.5(降方差)+ 验证过的合成 equation(破解的规则族,800 条,ratio 0.1);per-char 分词已弃(adapter-only 评测器不可行);**公 −0.006 / 私 +0.008 vs v14 → ~持平;危害最小的借鉴** |

### EQ1..EQ4 分析(赛后 equation 前沿网格,延迟提交窗口 100/队/天)

> equation 是唯一未解类(全员 hard-val ≤2/16,含 0.86 soup)。EQ-0 证明它是**单一全局 5 字符→1–4 字符
> base-36 密码**;EQ-2′ 三轮破解排除了全部简单代数族 → **强密码,无法从 7748 对样本用闭式还原**。于是 EQ-3
> 的经验性赌注:把 v14 骨架在**真实** equation 对上 SFT,看「覆盖式记忆」能走多远。下表「EQ1..EQ4」= 4 个
> SFT 网格 run(覆盖 × 剂量)。Δ 列对标 = **0.86/0.85 soup**(参赛最终选中的最好)。详见 `equation-frontier.md §8`。

| run | 假设 | 相对 v14 的改动 | hard-val | 公榜 | 私榜 | Δ vs 最好自训练 | LB 未显著提升的原因 | 教训 |
|---|---|---|---:|---:|---:|---|---|---|
| **EQ1 eq-spec** | SFT 1,555 个真实 equation **查询答案**(~16%)教全局密码 | + 1,555 query→`\boxed{}` 交织进 v14 | 0.167 | 0.85 | 0.85 | 公 −0.01 / 私 0.00 | 每题只监督**查询答案**(4 个上下文样例被 mask);equation ≈ 1/9,且只有「见过输入」那部分可学 | 仅查询覆盖 = 无聚合增益;equation 停在密码下界 |
| **EQ2 eq-aug** | **轮换**每个上下文样例为查询 → 真实对 ×5(7,814) | + 7,814 轮换真实输入→输出对(×1) | 0.194 | **0.86** | **0.86** | 公 0.00 / 私 **+0.01** | 覆盖到约 38%「符号全见过」的隐藏 equation 查询;其余多数是强密码(不可推断)→ 天花板是部分而非全部 | **覆盖是杠杆**:全局函数/查表类,SFT 全部真实对(样例→目标轮换)、单 epoch → 自训练私榜最好 |
| **EQ3 eq-hidose** | 同 1,555 加大**剂量**(×3) | 1,555 查询答案重复 ×3(~40%) | unknown | 0.84 | 0.84 | 公 −0.02 / 私 −0.01 | 无新信息(同 1,555 对重加权);过度加权挤占 replay 骨架 → 轻微回归 | **有剂量无覆盖反伤** —— 重复不加信号,稀释配方 |
| **EQ4 eq-aug-hidose** | 覆盖**和**剂量都拉满(7,814 ×2) | 7,814 轮换对重复 ×2 | unknown | 0.85 | **0.82** | 公 −0.01 / 私 **−0.03** | 连**好的**覆盖数据也过度加剂量 → 过拟合(私榜跌幅 ≫ 公榜) | **甜点 = 全覆盖 + 单 epoch**;×2 已过头 |
| soup_v2(eq-aug 入汤) | 把 eq-aug 入 0.86 soup,保稳健 + 加覆盖 | SVD(0.86-soup×0.6 + eq-aug×0.4)→ rank32 | unknown | 0.85 | 0.85 | 公 −0.01 / 私 0.00 | 入汤需**难尾稳健**成员;eq-aug 难尾弱(hard-val 0.194)→ 合并抄近路、平均掉覆盖 | **eq-aug 不可入汤** —— 覆盖增益只在独立 adapter 里成立 |

**结论:** equation **部分可解,未真正解决**。最好杠杆 `eq-aug`(全真实对覆盖、单 epoch)达 **0.86 / 0.86**
(全程自训练私榜最好),靠记忆「见过输入」那部分;但多数「未见输入」是强密码、不可推断。前沿是**有界**而非
开放;不破解规则(已证从样本不可行,EQ-2′)就触不到密码的未见尾部。LB 未跳的原因:equation ≈ 1/9 且只有一部分
可学,完美 equation 记忆器的聚合上限本就很小,且只覆盖见过的输入。

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

## lb1-v1 —— 第一名方法复现(2026-06-20)

> 在 `versions/lb1-v1/`(分支 `exp/nemo-postlb1-v1`)用纯 CPU 复现第一名方法。比赛已结束(不计排名),
> 这是方法验证 + 可复用方法论。LB1 是**训练数据方法**:真实的 `lb1-v1` LB 分数需要 GPU 训练一个 rank≤32
> adapter —— 该训练 + 受控的延迟提交作为明确的交接(preflight 闸门会一直阻止提交,直到一次完整训练产出
> 合法的 `submission.zip`)。保护的历史最佳:soup 0.86/0.85、v14 0.85、eq-aug 0.86/0.86。

| 检查项 | 结果 | 对照 writeup |
|---|---|---|
| 签名目录(100×100 × 22 非 join 规则) | **4,205 个签名 —— 完全一致**;`ABCCCDD`→15(add1/flip_add8/flip_add+1 6),槽位数字串逐字节一致 | 4,205 ✓ |
| **equation-numeric 重新探测**(真实 train.csv) | **deduce 566/596 = 95.0%**,guess 65/136 = 47.8%;deduce/guess 划分 596/136 完全一致 | 95.5% / 52.9% |
| HEX 压缩 | `1101000001`→`341` 一致;约 75% 字符削减 | 一致 |
| bit 规则序列目录 | 纯枚举 **857,692 序列 / 115,826 函数** —— 大幅超出;LB1 的 5,238 是**针对 train.csv 调过的子集**,无法从文字复现。修复(Hamming-NN)机制已验证(可恢复 Hamming-3 的破坏)。 | ≈5,238(未复现) |

**equation 结论修正。** EQ-0/EQ-2′「全局密码 = 不可解」的结论**过度泛化**了:它对 *guess*(未见算符)
子集成立(~48–53%),但 **equation-numeric *deduce* 可按每题用 24 规则清单 + 观察 1/2 解出 95%** —— 不是
单一全局函数。这与 LB1 的覆盖率表一致,推翻了我们对 deduce 子集的判断(见 `gap_analysis.md`、
`equation-frontier.md`)。到 0.92 的关键剩余差距是 cryptarithm + bit 的**数据量**(LB1:220k+140k 合成,
约 170h 单卡),只能作为赛后缩小规模的方法验证运行来复现。

## lb3-v1 — LB3(第3名)方法实现(2026-06-20)

> 分支 `exp/nemo-postlb3-v1`,代码在 `versions/lb3-v1/`,纯 CPU 复现 LB3(Private 0.900)方法。
> **比赛已于 2026-06-15 截止**,故**未做线上提交**(preflight 门正确拦截:比赛关闭 + 无完成的 GPU 训练
> → 无 `submission.zip`)。本版只验证*机制*,不复现 0.900。已保护最佳成绩:soup 0.86/0.85、eq-aug 0.86/0.86。

实测结果:
- **equation-numeric 重测(真实 train.csv,732 题)**:deduce 566/596 = **95.0%**,guess 65/136 = 47.8%
  → 第二次独立反驳"全局密码不可解"结论(deduce 子集可解,见 `equation-frontier.md`)。
- **CSP cryptarithm**(合成 n=150):`*` deduce **100%**(映射全恢复 100%);`+` 98%;`-` 94.7%;`*` guess 94%。
- **bit HEX+尾2位** 压缩:解 100%,trace token **−23.4%**(LB3 参考 ≈ −25%)。
- **numeric 13-op**:deduce **98.3%**(guess 11%,合成场景缺少官方生成器的算子族共现结构)。
- **私有榜对齐验证**自检通过:10% 分层留出 + 防泄漏 + perfect-trace-rate + adapter rank≤32/zip 结构。

剩余到 0.900 的关键差距 = **两阶段(记忆→执行)训练** + cryptarithm 数据量(LB3 ~58 GPU-h),
需在授权后做降配 GPU 方法验证(已作为 handoff 文档化,见 `versions/lb3-v1/README.md`)。

## lb5-v1 — LB5(第5名)方法实现(2026-06-20)

> 分支 `exp/nemo-postlb5-v1`,代码在 `versions/lb5-v1/`,纯 CPU 复现 LB5(Private 0.900,
> "无限生成器 + 迭代 LoRA 平均")方法。**比赛已于 2026-06-15 截止**,故**未做线上提交**:
> guarded submit 经真实 `kca kaggle submit` 执行并被 preflight 门正确拦截,BLOCKED 决策已写入
> `.agent/kca/audit.jsonl`。本版只验证*机制*。已保护最佳成绩:soup 0.86/0.85、eq-aug 0.86/0.86。

实测结果:
- **equation 重测(真实 train.csv,732 题)**:deduce 566/596 = **95.0%**,guess 47.8%
  → **第三次**独立反驳"全局密码"结论(继 LB1 95.5%、LB3 93.3%)。
- **LB5 方程求解器**(2-world/4-family/13-rule,合成 n=300):deduce **99.7%**(guess 20.7%,合成偏难)。
- **三元 raw-bit 求解器**(15 原语 = 8 二元 + 7 三元):binary/ternary 均 **100%**;**7-example 截断不掉点**。
- **tokenizer 探针**:合并 token 编码(`5A`/`AB`)判为高风险 → 用 raw bits(LB5 负面教训)。
- **无泄漏生成器**:拟合 train 统计(bit 1602 / eq 1555),无泄漏校验 PASS(vs 9500 prompts)。
- **私有榜对齐(无泄漏)验证**自检通过(soup 稳定性代理确定性 + adapter rank≤32/zip 结构)。

LB5 与 LB1/LB3 的区别:**不靠 cryptarithm**(7.9%)也能到 0.90,靠把 bit(三元)+ equation + 简单类
做满 + 迭代 LoRA 平均/多种子 soup 稳定化;到 0.92 的差距仍是 cryptarithm。GPU 三阶段训练为 handoff
(`versions/lb5-v1/train_phases.py`,GPU-gated)。

## lb6-v1 — LB6(public 第2 / private 第6)方法实现(2026-06-20)

> 分支 `exp/nemo-postlb6-v1`,代码在 `versions/lb6-v1/`,纯 CPU 复现 LB6 方法。
> **比赛已于 2026-06-15 截止**,故**未做线上提交**(guarded submit 经真实 `kca kaggle submit` 执行并被
> preflight 门拦截,BLOCKED 写入 `.agent/kca/audit.jsonl`)。只验证*机制*。已保护:soup 0.86/0.85、eq-aug 0.86/0.86。

实测结果:
- **equation 重测(真实 train.csv,732 题)**:deduce 566/596 = **95.0%**,guess 47.8% → **第六次**独立反驳"全局密码"。
- **LB13 方程求解器**(4 互斥族 + 全局多数投票 reversal;合成 n=300):deduce **100%**;guess 84.7%(合成互斥更干净)。
- **鲁棒 vs 严格聚合(转写噪声下)**:**鲁棒 100% vs 严格 54%** —— LB13 保留噪声 trace 的关键杠杆,已直接验证。
- **三输入 bit 验证器**(MAJ/XNOR3 + 位搜索 + 左缘回退;n=300):解 **100%**。
- **保留失败样本 1:1 再平衡**:4.26:1 → **1.00:1**(全部保留 teacher-incorrect)。
- **验证**自检通过(teacher oracle、鲁棒>严格、再平衡、perfect-trace-rate、adapter rank≤32 preflight)。

LB13 独特贡献:全局多数投票 reversal + 鲁棒 ≥1 聚合(批次最佳 guess 50.7%)、三输入 bit 验证、
**保留 teacher-incorrect 并 1:1 再平衡**(挑战我们 c1/c2 仅保留正确样本的过滤;A/B 为推荐的 GPU 后续)。
GPU 三阶段递减 LR SFT 为 handoff(`versions/lb13-v1/train_3stage.py`,GPU-gated)。
- **equation 重测(真实 train.csv,732 题)**:deduce 566/596 = **95.0%**,guess 47.8% → 再次反驳"全局密码"。
- **DUMMY 掩码逐域归因**(招牌杠杆,**修复 B8** "单类增益≠总增益"):隔离每个域的信号,非目标域输出
  `\boxed{DUMMY}`;0.01 LB ≈ 3 题。
- **模板 bit 求解器**(shl/shr/rotr × pairwise/ternary,hex 速查表):pairwise+shift **99.5%**,ternary **100%**。
- **DFS cryptarithm**(反向搜索 + 前导零/个位/方程排序剪枝):`*` **100%**,`+` 93%(反向 pass 为真实反向结构的回退)。
- **LB6 方程求解器**(add/sub/mul + **maxmodmin** 族):deduce **100%**(guess 47.7%,合成)。
- **bit/cryptarithm 取舍 CV**:预测加倍 cryptarithm 使 bit-CV 掉 +0.082 → "需加倍 bit 才能保住 CV"(LB6 选择遗憾)。
- **验证**自检通过(full-train-as-validation + DUMMY 探针 + perfect-trace-rate + adapter rank≤32 preflight)。

GPU 单轮 Unsloth SFT(BS32/LR3.5e-4)为 handoff(`versions/lb6-v1/train_lb6.py`,GPU-gated)。

## lb10-v1 — LB10(public 0.860 / private 0.880)方法实现(2026-06-20)

> 分支 `exp/nemo-postlb10-v1`,代码在 `versions/lb10-v1/`,纯 CPU 复现 LB10 方法。
> **比赛已于 2026-06-15 截止**,故**未做线上提交**(guarded submit 经真实 `kca kaggle submit` 执行并被
> preflight 门拦截,BLOCKED 写入 `.agent/kca/audit.jsonl`)。只验证*机制*。已保护:soup 0.86/0.85、eq-aug 0.86/0.86。

实测结果:
- **equation 重测(真实 train.csv,732 题)**:deduce 566/596 = **95.0%**,guess 47.8% → 第五次反驳"全局密码"。
- **旋转/移位 key-table bit 推理器**(单操作数 `out[i]=F(rotl(x,a),shl(x,b),shr(x,c))`,n=200):
  8 例 **96.5%**、16 例 **100%**;**8 个 key 全覆盖后 oracle ~98–100%**("先把 teacher 做强"的天花板)。
- **LB10 方程求解器**(频率排序 deduce + 双轴 guess;n=300):deduce **99.3%**。
- **oracle-vs-fidelity + logprob** 诊断:把 teacher 天花板与模仿差距分开;低 logprob 脆弱样本标记优先 2×。
- **保留失败样本 + 按验证选择**:未解 teacher trace 保留(不过滤);验证自检通过(adapter rank≤32 preflight)。

LB10 独特贡献:**"先把 teacher 做强"**(先抬每类 oracle 覆盖率 = 分数天花板)、**旋转/移位 key-table**
bit 推理器、**oracle 天花板 vs 模型 fidelity + logprob 可学性**诊断。两个 A/B 留给 GPU 后续:保留失败 vs
仅保留正确(挑战我们 c1/c2)、LoRA 合并(LB10 报告合并失败)。GPU SFT(alpha/r=4,2 epoch)为 handoff
(`versions/lb10-v1/train_lb10.py`,GPU-gated)。












## lb13-v1 — LB13(第13名)方法实现(2026-06-20)

> 分支 `exp/nemo-postlb13-v1`,代码在 `versions/lb13-v1/`,纯 CPU 复现 LB13(teacher oracle 89.4%)。

## lb25-v1 — LB25(huikang Progress-Prize 改进)方法实现(2026-06-20)

> 分支 `exp/nemo-postlb25-v1`,代码在 `versions/lb25-v1/`,纯 CPU 复现 LB25 方法。**已实现:** LB25
> 的 next_version_plan 版本即 `v16-evalfix`,已于 2026-06-20 训练 + 提交 → **public 0.832 / private
> 0.828,低于 0.86 历史最佳("假设不成立")**;本目录是这五个 lever 的干净可复用封装,不是预期超过 0.86 的新方法。
> 五个 lever:#1 eval/submission prompt 一致性审计(`eval_parity.py`,headline,可复用 GPU-free 工具,
> = 我们的 B4/INS-002);#2 equation 反转对称性(`eq_reversal.py`,真实 train.csv 上 573/596 = 96.1% 单模式,
> 搜索减少 47.6%);#3/#4 简单类别 + cipher-prefix 合成(`easy_cat_synth.py`,240/240,仅防回归);
> #5 重组并自验证的 bit CoT(`bit_cot.py`);min-logprob replay(≤15% dose)。共享模块从 lb1-v1 复用。
> LB25 方法的真实 LB 结果已存在(v16-evalfix);重新 GPU 训练只会复现已知的低于最佳的数值。历史最佳未动。

