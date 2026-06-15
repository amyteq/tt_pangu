# Tracking (中文存档 / zh sidecar)

> 本文件**逐字保留** GitHub issue #87 正文(中文:协作机制 + 状态快照 + 🟡 Open Discussion + 📌 TODO/Plan +
> 📐 §9 评估 + 📚 Reference + 实战案例 + 折叠表)的快照,仅供历史保存。英文规范版见 [`tracking.md`](./tracking.md);
> 实时讨论见 issue #87(保持开放)。快照来源:issue #87 body,导出于 2026-06-14。

---

**Kaggle [Orbit Wars](https://www.kaggle.com/competitions/orbit-wars) 长期跟踪与策略讨论帖**($50k Featured,1v1 天梯,截止 **2026-06-23**,终评再跑 ~2 周)。方向讨论在这里进行,我负责维护下面的状态与表格。

## 🤝 协作机制(inline 更新约定)

1. **🟡 Open Discussion 表 = 阻塞项**:需要 Harry 拍板。直接 comment 一句即可(如 `D1=C`、`D3 同意`),我读到后把结论**回写进表格**并解锁对应任务。
2. **📌 TODO/Plan 表 = 工作队列**:Harry 在 comment 里给意见/调整优先级,我推进并维护状态列。
3. **Inline 更新**:
   - issue 正文:我每次用 `gh issue edit` **原地更新**(不刷屏),正文顶部标注 `最后更新` 时间。
   - 我的 comment:只维护**一条「📜 工作日志」comment**,原地追加,不发新楼。
   - 你的 comment:我处理后默认在表格里回写结论 + 标注来源;若你同意,我也可以直接在你的 comment 末尾追加 `✓ 已纳入 <日期>` 标记(首次会先验证编辑权限)——是否启用见 D5。

> 最后更新:2026-06-12(第 10 版:实战案例 #2(top-8 画像+对抗验证:顶部全是规则引擎);T12 v2 完成(recall 0.387 但竞技场 0%,BC 偏移实锤);天梯裁决:t14 兑现 +39 / co-arrival 判负 -44;may 替换提案待确认)

---

## 📊 状态快照(2026-06-12)

比赛只保留**最近 2 个提交**参与天梯。当前:

| 提交 | 说明 | 天梯分 | 备注 |
|---|---|---|---|
| **kuni05-重提**(2026-06-12) | 公开 LB-1240.5 agent(**已注明出处**) | 从 600 重爬(旧条目峰值 **1137**) | D2 保槽重提;旧 1137 条目已退役但峰值记录在案 |
| **v3.2**(2026-06-12,新) | **自研** Forecast,t14 调参版 | 从 600 起爬(预期 > v3 的 686) | T2-R2 产物:+7pt vs evogen 双块确认,6 门 PASS 后提交 |
| 已退役:旧 kuni05 / Forecast v3 / v2.1 | — | 峰值 1137 / 686 / 556 | 最后 3 天冻结时按峰值记录选最终 2 个重提 |

LB 头部 ≈ **1713**,top-10 ≈ 1500-1600。**当前瓶颈(cliff)**:对弱 agent 胜率 ~100%,对强档(evogen 1093 / multifocus / kuni05 1240)只有 **0-15%**。已系统性试完 5 个增量杠杆(详见折叠表),全部无法跨越 cliff —— 强档靠的是**一体化协同规划系统**,不是可移植的单一机制。**方向已定:D1=C(低成本继续)。**

---

## 🟡 Open Discussion —— 待 Harry 确认(unblock)

| ID | 议题 | 背景/选项 | 我的建议 | 状态 | 结论 |
|---|---|---|---|---|---|
| **D1** | **总方向** | **A** 维持现状收尾;**B** 全面重写协同规划器;**C** 低成本继续:replay mining + suite 上系统化参数优化 | 有余力则 **C** | ✅ 已确认 | **C**(2026-06-12,[comment](https://github.com/amyteq/tt_pangu/issues/87#issuecomment-4682508952))→ 解锁 T1/T2/T4,并纳入 T8/T9 |
| **D2** | **提交位策略** | latest-2 现为 [Forecast v3 ~686, kuni05 ~1137];再提交任何版本都会挤掉其一。deadline 06-23 前最后窗口怎么用? | 保持现状;最后 24-48h 视 C 成果决定是否用一个位换自研最强版 | ✅ 已确认 | **两个现役版本分数已稳定(记录在案:kuni05 ~1137 / Forecast v3 ~686,2026-06-12)。本地测试通过且有提高的版本尽量提交;最后 3 天前选定最终 2 个最佳版本重复提交**(2026-06-12,[comment](https://github.com/amyteq/tt_pangu/issues/87#issuecomment-4682738736)) |
| **D3** | **算力** | T2 大规模优化(数千局)可在 snorlax(RTX 4090 机,24 核 CPU)上跑;GPU 对引擎无用,纯吃 CPU | 同意则我准备可在 snorlax 跑的脚本 | ✅ 完全解锁 | **同意**(2026-06-12)。SSH 已由 Harry 提供并验证可用([comment](https://github.com/amyteq/tt_pangu/issues/87#issuecomment-4682633197)):`rc.py -s snorlax` 开机 → `ssh snorlax` 直连;实测 24 核 / 123 GiB / RTX 4090 在线;资源与远程操作已写入 **[docs/tooling/remote-compute-snorlax.md](https://github.com/amyteq/tt_pangu/pull/89)**(PR #89)+ agent 记忆,多比赛可见 |
| **D4** | **RL/蒸馏路线** | torch 在评测端**实证可用**(kuni05 带 torch 上分 ~1137);RL 自博弈/蒸馏技术上可行但高风险 | 暂缓;只在 B 框架下再评估 | ✅ 已确认 | **在 snorlax 上试 RL/蒸馏;若胜过现役版本(过 T10 验证门)才提交**(Harry,2026-06-12 session)→ 立项 **T12**;snorlax torch 2.10+CUDA 已验证 |
| **D5** | **comment 标记权限** | 是否允许我在你的 comment 末尾追加 `✓ 已纳入` 标记(inline 处理回执) | 可选;不启用则只在表格回写 | ✅ 已确认 | **允许,且优先在 comment 内 inline 标记**(2026-06-12)。已对 3 条历史 comment 补打回执,编辑权限验证通过;后续每条处理完即标 |

---

## 📌 TODO / Plan / Direction —— 回 comment 后我推进

| ID | 任务 | 前置 | 状态 | 备注 |
|---|---|---|---|---|
| T2 | **Suite 上系统化参数优化**(调 `OW_*` 旋钮) | D1=C ✅ | ✅ **R2 阳性收官(t14 → v3.2 已烘焙+提交)** | 3 阶段共 ~2,800 局(R1 随机 21 配置 / R2 细化 9 配置 / R3 终局 3 配置×300 局):**无配置显著胜过 baseline**(11.3±3.6 vs 10.3±3.4,t05 5.3 更差);R1/R2 的 "25%" 系小样本噪声+选择偏差,被 ±7pt 烘焙门槛正确拦下。功效协议已固化进 [`sweep_opt.py`](https://github.com/amyteq/tt_pangu/blob/worktree-orbit-wars/competitions/orbit-wars/arena/sweep_opt.py)(commit `cb52e34`)。旋钮空间在 baseline 附近已饱和 → 资源转 T8;**T2-R2 完赛(2026-06-12):阳性!** snorlax 功效搜索(26 配置×300 局,种子 13000+)TOP=t14 17.7%;本地全新块(15000+)确认 **19.0±4.4 vs 基线 12.0±3.7(+7.0pt,过烘焙线;三块合并 17.3% vs 11.7%,z≈3.3)** → **烘焙为 v3.2**(H26/FF5/FD20/CE3.2/CL1.3,[`d3e3f09`](https://github.com/amyteq/tt_pangu/commit/d3e3f09)),VALIDATION 6 门全 PASS(4p avg_rank 1.01,p99 8.3ms),**已提交天梯** |
| T8 | **真·同步到达攻击(co-arrival)** ⚠️ Harry 点名重点(§9-4) | D1=C ✅ | ✅ 收官(v1/v2 均 +3pt 量级,默认 OFF) | `OW_COARRIVAL`:枚举到达回合 K,最远源立即发射、近源**预留并延后发射**(无状态重规划:在途波次出现在投影到达表,近源 ETA 与倒计时相等时自然开火),同回合到达合兵作战。**两轮 A/B(全新种子块):R1 18.3% vs 13.3%(300 局/配置);R2 14.3% vs 12.2%(600 局/配置);合计 15.7% vs 12.6%(+3.1pt,900 局/配置,两轮同号)**;starter 86-89% 无回退。**判定:真实但幅度未过 +7pt 烘焙线 → 保持 env-gate OFF,迭代方向:K±1 容差合流、COARR_HOLD>1 占领后驻防、多波次**。**强档 A/B 完赛(各 300 局):vs multifocus 0%→0%、vs kuni05 0%→0%,co-arrival v1 撼不动顶档,增益限 evogen 层**。**v2(K±1 容差合流)A/B 完赛(种子 14000+,300 局):14.7% vs 12.0%(+2.7pt)≈ v1,无叠加增益([`0baa21d`](https://github.com/amyteq/tt_pangu/commit/0baa21d))→ T8 收官:co-arrival 为 evogen 层 +3pt 量级杠杆,保持默认 OFF** |
| T9 | **§7 架构件落地 → v4 "Scheduler"**(与 T13 合并实施) | D1=C ✅ | 🟢 **平台已建,平价确认,迭代中** | 设计经 3-agent red-team(beam 核心被证伪:守恒终值给物流恒 0 价值)→ **hub-and-hammer 策略层**([`261a7a6`](https://github.com/amyteq/tt_pangu/commit/261a7a6)):ledger 精确出兵量+能力先验 / 枢纽蓄力 / 0.9 档重锤 / 后方流送豁免预算 / **事件日志(Logger ✅)**。iter1 镜像 13%(日志诊断:83% 在途+碎锤)→ iter2 护栏 → **150 配对种子确认 = 与 v3.2 平价(49.3%),无任何回退**。下一刀:锤时机(对手在途反击窗)/ 锤目标集群 / FM3 对手响应项 |
| T10 | **本地 test/validation 清单**(`VALIDATION.md`):提交前必过的 arena 门 + 协议 | 无 | 🟢 进行中 | Harry 指示:本地测试通过**并有提高**才提交;含 suite 门、配对种子功效协议、4p 鲁棒性、运行时/崩溃检查 |
| T11 | **动态防守 reserve 增强**(§9-2,Harry 点名重点):用前向模拟统一管理防守缺口,替代启发式 threat 投影 | 无 | ❌ 账本约束版 = no-op | `OW_LEDGER`(出兵量 ≤ do-nothing 投影各持有回合最小驻军,只收紧不放宽)A/B 300 局:**两臂逐局完全相同**——约束从不触发(在途 threat reserve + 在途上限已覆盖)。诚实记录;§9-2 深层版(全局 ThreatLedger+增援调度)并入 T9 再议 |
| T12 | **RL/蒸馏路线**(D4 ✅):①行为克隆 kuni05(teacher)→ 轻量策略网;②可选自博弈 RL 微调;③过 T10 门且胜过现役才提交 | D4 ✅ | 🟢 Phase A 启动 | 数据生成器 `arena/distill_gen.py` 已建并冒烟通过(876 样本/4 局);Phase A ✅(53,873 样本)→ **Phase B v0 完赛**:解码-特征-训练-学生 agent 全管线落地([`dc9f362`](https://github.com/amyteq/tt_pangu/commit/dc9f362));13.45M 配对样本训练 16-64-64 MLP;**v0 实测:25% vs starter、0% vs v2.1/evogen —— 配对 BC + 粗特征复刻不了教师的协同规划**(印证 D4 高风险预估)。下一迭代:前向模拟特征(到达时刻守军/可占性)、set-attention、DAgger;按 D2/D4 标准 v0 远不够提交 |
| T13 | **动态战略识别与反制** | 无 | 🟢 并入 v4(T9) | 姿态机 v1 ❌(-2.7pt);red-team 裁定 C3 砍出 iter1(ledger 已含其防守半边);**反击窗(对手主力在途他处时出锤)列为 v4 下一刀**,风格分类器随后 |
| T14 | **短跳供应链**(replay 启示②):增援只许 ≤25 距离短跳、只往前线方向、持续小股 | 无 | 📋 排队(OVERKILL A/B 之后) | 与被否决的 CONSOLIDATE(长途激进版)区分;Jake Will 56% 发射为此类 |
| T1 | **Replay mining**:挖[公开 episode 数据集](https://www.kaggle.com/datasets/kaggle/orbit-wars-episodes-2026-06-08)顶级 bot 行为 → 启发式参数 | D1=C ✅ | 📋 排队 | 排 T2/T8 之后(数据下载+解析较重) |
| T4 | **Endgame + Comet 模块**(450-500 回合只做 score-positive;彗星回本门控) | D1=C ✅ | 📋 排队 | 小而独立,suite 门控 |
| T5 | **天梯监控 + 本帖状态表维护** | 无 | 🟢 进行中 | 含 kuni05/Forecast 分数追踪 |
| T6 | 确认评测端 torch 可用性 | 无 | ✅ 完成 | 实证:torch 版 kuni05 上分 ~1137 |
| T7 | 2p/4p 分策略 | 无 | ❌ 否决 | 天梯只计 **1v1**;4p arena 仅留作鲁棒性测试 |
| T15 | **彗星轨迹预测**(§9-1 缺口):建模 `comets` 路径运动 → 喂进 `project()` 扫掠碰撞 + `_path_blocked`(现状:彗星整体排除出投影) | 无 | 📋 立项(2026-06-14)**先测量后建** | 先用 episode 数据集量化彗星出现率 + 决定胜负的比例,再决定是否建;env-gate `OW_COMET` |
| T16 | **绕日/绕星 waypoint 路由**(§9-1 缺口):直线路径被挡时不再单纯放弃 → 切线重瞄 或 1-hop 中继 | 无 | ◻︎ **已测量 → PARK**(2026-06-15) | 插桩孪生 `forecast_measure.py`(8/8 行为一致)跑 80 局:被 `_path_blocked` 丢弃的价值为正发射很频繁(starter 107/局、mirror 639),但可恢复价值经 3-agent 对抗复核 = **乐观上界 17–26% → 现实 6–15%**(仅 35.5% "可恢复"丢弃为正值;**41% 被丢目标 5 回合内仍被占下**;重瞄折损)。**≈1.4–2.7pt 胜率 < +7pt 烘焙线**,与 T8 co-arrival 同样的"频繁离线缺口→天梯归零"机制。仅当 v4 停滞时用 gate-only 原型重启。工具 `arena/measure_t16.py` |

状态图例:⏸ 待确认 / 📋 已解锁排队 / 🟢 进行中 / ✅ 完成 / ❌ 否决

> **设计原则(Harry,2026-06-12)**:算法设计尽量**同时适配 2p/4p**,不做分策略 —— 机制(差分价值、防守 reserve、co-arrival)都按"与玩家数无关"实现:模拟器/combat 解算本就支持多方,目标枚举遍历所有非己方玩家;4p arena 作为每个候选版本的鲁棒性测试(进 T10 清单),不单独养一套 4p 策略。

---

## 📐 ChatGPT §9 优先级完成度评估(应 Harry 要求,2026-06-12)

| §9 优先级项 | 完成度 | 已有 | 主要缺口 |
|---|---|---|---|
| 1. 精确几何 + ETA | **~85%** | 不动点拦截解算;引擎级速度公式;太阳/星球路径遮挡;**bit-exact 前向模拟**(swept 碰撞,对真引擎 3,672 单元 0 误差) | 绕日 waypoint 路由(被挡即放弃、不绕行)→ **T16 立项**;彗星轨迹预测(彗星整体排除)→ **T15 立项**(均 2026-06-14,先测量后建) |
| 2. 动态防守 reserve | **~70%** | 在途威胁 reserve;v3.1 模拟驱动增援;**T11 账本约束已验证 = no-op(现有 reserve+在途上限已覆盖该风险,300 局两臂逐局相同)** | 深层 ThreatLedger 统一时间轴并入 T9;replay 启示:防守的高阶形态是"决战聚兵"(对手大军在途时收缩集结)→ T13 |
| 3. ROI 扩张 | **~90%** | v3 终态差分净船值**涵盖并超越**静态 ROI;556→686 的主要来源 | 开局序列优化(已试,齐射式失败) |
| 4. 同步攻击 | **~80%(已做完并定论)** | **真 co-arrival 已实现并三轮 A/B**(`OW_COARRIVAL`+K±1 容差):evogen 层稳定 +3pt,顶档 0 增益,未过烘焙线 → 默认 OFF;may 账号 v3_2_coarr 在天梯实测中(爬分有希望) | replay 修正:同步**形式**不值钱,**单击绝对规模**才值钱 → 资源转 OVERKILL(进行中)+ T14 供应链 |
| 5. 2p/4p 分策略 | **不适用** | 已确认天梯只计 1v1(配对 μ 更新);4p arena 已建留作鲁棒性 | —(研究完成,功能不需要) |
| 6. 本地大样本验证 | **~80%** | 并行竞技场(30-40×、确定性);同种子双座位(≈paired-seed);held-out 种子纪律;**天梯预测套件**("自博弈不预测天梯"教训的产物) | 战术事件日志;无效舰队率/核心失守率等细粒度指标;500+ 局常态化(→T9/T2) |
| 7. 轻量可解释快速线上代码 | **~95%** | 单文件 stdlib-only;~4ms/回合(预算 1000ms);崩溃安全包装;self-play 零报错 | 基本无 |

**§7 架构对照**(Harry 点名探索):StateParser ✅ / GeometryEngine ✅(85%) / **ThreatLedger ◻︎ 部分**(有 reserve+翻盘检测,缺统一时间轴→T9) / CandidateGenerator ✅(单步) / ActionEvaluator ✅(差分价值) / **Scheduler ◻︎**(有源预算扣减,缺跨动作冲突调度) / **MetaPolicy ◻︎**(仅 phase cap) / **Logger ❌**(→T9)。
**§6.1 本地 tournament harness**:已建成且为核心方法论(并行 arena + suite gate),见第 6 项。

---

## 📚 Reference

| 文档 | 链接 | 说明 |
|---|---|---|
| Claude 初始分析与计划(A1) | [`dev/temp` → temp/orbit-wars-analysis-claude-a1.md](https://github.com/amyteq/tt_pangu/blob/dev/temp/temp/orbit-wars-analysis-claude-a1.md) | 赛制拆解 / 机制要点 / 分层路线(模拟器→启发式→搜索→RL) |
| ChatGPT 独立分析(A2) | [`dev/temp` → temp/orbit-wars-analysis-chatgpt-a2.md](https://github.com/amyteq/tt_pangu/blob/dev/temp/temp/orbit-wars-analysis-chatgpt-a2.md) | 模块化架构(ThreatLedger 等)/ v0-v6 实验路线 / paired-seed 评估纪律 |
| 完整实验日志(README) | [competitions/orbit-wars/README.md @ PR#80](https://github.com/amyteq/tt_pangu/blob/b9228723ef69ef5e4ac7ca5458c65dc9803b73b0/competitions/orbit-wars/README.md) | TL;DR + 按时间线的全部实验/死路/证据 |
| 代码 PR | #80(**已合并**,2026-06-12 squash) | agent + arena + EPISODES.md + utils.py 全部入 main;远程分支留审计 |
| 天梯预测门 | [arena/suite_gate.py](https://github.com/amyteq/tt_pangu/blob/worktree-orbit-wars/competitions/orbit-wars/arena/suite_gate.py) | 强弱跨度公开 agent 套件;离线胜率 ≈ 天梯 |
| kuni05 notebook(LB 1240.5) | [kaggle.com/code/kuni05/…](https://www.kaggle.com/code/kuni05/lb-1240-5-orbit-wars-producer-agent-submission) | 我们条目的来源(已注明出处);强档研究对象 |
| evogen notebook(LB 1093) | [kaggle.com/code/penguin069/evogen-v5-1093](https://www.kaggle.com/code/penguin069/evogen-v5-1093) | 最弱强档;opening DFS + 多源 commitment 研究对象 |
| 比赛页 / 规则 | [overview](https://www.kaggle.com/competitions/orbit-wars) / [rules](https://www.kaggle.com/competitions/orbit-wars/rules) | id 138420;每日 5 提交;latest-2 计分 |
| `dev/temp` 分支 | [branch](https://github.com/amyteq/tt_pangu/tree/dev/temp/temp) | 临时文档暂存;**不触发任何 CI**(workflows 仅 main push / PR / dispatch),push 即生效 |
| snorlax 算力节点文档 | [docs/tooling/remote-compute-snorlax.md](https://github.com/amyteq/tt_pangu/pull/89)(**PR #89**) | 24 核 / 123 GiB / RTX 4090;`rc.py` 开机 + `ssh snorlax`;vllm 占 GPU 注意事项;T2/T8 大样本验证用 |

**交叉引用(相关 PR / issue)**:#80(本比赛全部代码,review-only)· **#89**(snorlax 算力文档)· [#83](https://github.com/amyteq/tt_pangu/issues/83)(Kaggle 配额之外的算力探索 —— snorlax 即其本地解之一)· [#86](https://github.com/amyteq/tt_pangu/issues/86)(Nemotron 兄弟跟踪帖,同款协作机制)· [#77](https://github.com/amyteq/tt_pangu/issues/77)/[#78](https://github.com/amyteq/tt_pangu/issues/78)(kca 提交链路已知缺口,影响所有比赛的自动提交)


## 🎬 实战案例分析(tracking)

| # | Episode | 对局 | 分析 | 核心 insight | 落实情况 |
|---|---|---|---|---|---|
| 1 | [79586066](https://www.kaggle.com/competitions/orbit-wars/leaderboard?submissionId=53517858&episodeId=79586066) | 213tubo vs **Jake Will**(胜,t190 全灭) | [分析 comment](https://github.com/amyteq/tt_pangu/issues/87#issuecomment-4686194575) / [机制六问](https://github.com/amyteq/tt_pangu/issues/87#issuecomment-4686336440) | ①少而重(27×78船)>> 多而小(117×19船);②增援占 56% = 短跳供应链;③同到达形式不值钱,单击规模才值钱;④角落星(prod1/驻45)= ROI 陷阱;⑤贴日飞行 = 败者崩盘信号 | ① → `OW_OVERKILL` 已实现,功效 A/B 进行中;② → T14 立项;③ → 修正 T8 预期;④⑤ 价值门/路径门已天然覆盖 |

| 2 | 批量:top-8 × 40 局(320 局画像 + 64 局对抗深检) | Isaiah @ Tufa Labs / Hober Malloc / Controlvector / typeIIIfairy / Boey / OMWM / Jake Will / 213tubo | — | **技术路线判定:top-6 全部为规则/搜索引擎,无 NN 迹象**;风格分型:Isaiah=积分马拉松(97.6% 胜局不灭对手,双档出兵)、Hober=滚雪球供应链(88% 增援、95% 精确全掏)、Controlvector=流转储备+重锤(巨舰 78% 自家调度) | [EPISODES.md 分析 #2](https://github.com/amyteq/tt_pangu/blob/worktree-orbit-wars/competitions/orbit-wars/EPISODES.md);Isaiah 双档出兵列为候选机制;BC 路线降级证据 |

> 批量管线就绪:`kaggleusercontent.com/episodes/<id>.json` 下载 + bit-exact 解码统计,每局 ~1 分钟;top-range episode 持续补充中。

---

<details>
<summary>🧬 Agent 演进与天梯结果(点开)</summary>

| 版本 | 思路 | 离线 | 天梯 | 结论 |
|---|---|---|---|---|
| v1 | 拦截解算 + 精确占领数学 + ROI 扩张 | 88% vs starter | ~385→538 | 被替代 |
| v2 | “拿住才算”:在途上限 1.2× + 前线驻军(修复漏水扩张) | 92% vs starter | ~626 | 被替代 |
| v2.1 | 分阶段在途上限(2.0→1.0) | 200 局 ~打平 | **556** | 无真实增益 |
| **v3** | **Forecast**:bit-exact 前向模拟 + **终态差分净船值** + 模拟防御底线 | **91% vs v2.1** | **~686** | **自研最佳** |
| v3.1 | v3 + 模拟驱动防御增援 | 自博弈 62-66% vs v3 | suite 上 ≈ v3 | 仅自博弈增益;现 `main.py` |

核心资产:**bit-exact 前向模拟器**(对真引擎 3,672 个 planet-step 单元 0 误差)+ 守恒正确的终态差分价值函数 → 556→686,通杀弱档。
</details>

<details>
<summary>🧪 实验/杠杆跟踪表(点开)</summary>

| 杠杆 | 状态 | 在天梯预测套件上的结果 |
|---|---|---|
| 前向模拟差分价值(v3) | ✅ 保留 | 唯一大增益(556→686,通杀弱档) |
| 分阶段在途上限(v2.1) | ◻︎ 中性 | ~打平(无害,保留) |
| 防御增援(v3.1) | ◻︎ 仅自博弈 | 自博弈 +62%,套件上 **0 增益** |
| 合并兵力(闲置后方→前线) | ❌ 否决 | 从未胜过 v2.1;默认 OFF |
| safe_drain 出兵量 | ❌ 否决 | 倒退(无价值门控时过度摊薄扩张) |
| 多源**齐射**(同回合多源) | ❌ 无增益 | 对强档仍 0%;⚠️ 注:未做 ETA 对齐,**不等于否定 co-arrival**(→T8) |
| 开局序列规划器 | ❌ 无增益 | 出手多了(25 回合 9 次 vs 2 次)但胜率反降 |
| `PROJ_H` 视野扫描 | ❌ 无增益 | 更长反而更差(18→15.6%,30→3% vs evogen) |
| `OW_*` 参数随机搜索(T2-R1) | ❌ 无增益 | 300 局终测无配置胜 baseline;**教训:同配置批间波动 8-27%(24-60 局批)→ 一切对比需 ≥150 配对种子(±3.5pt)** |

**规律**:5 个移植自强档的单点杠杆全部失效 —— 强档赢在**一体化系统**(开局搜索 + 多波次 + supply + 模拟协同设计),不是单机制。
</details>

<details>
<summary>🔑 方法论结论(可复用)+ 强档研究(点开)</summary>

- **自博弈不预测天梯**:v3 离线赢 v2.1 91%,上天梯初期几乎同分(561 vs 556)。建了**强弱跨度公开 agent 套件**(random→starter→adilshamim→pub_tactical→evogen1093→multifocus→kuni05)后,离线胜率才与天梯对齐(我方 ~54% ≈ ~560-690;kuni05 89.6% ≈ ~1137)。**一切改动用套件门控,不用自博弈。**
- **并行竞技场**(`arena/pool.py`):~30-40× 提速,确定性可复现,2p+4p。引擎是纯 Python CPU 负载,**GPU 无用**,用 `--procs` 吃满核。
- **天梯确认为 1v1**(评分更新是配对 μ);4p 存在但不计分。
- **强档怎么赢**(研究了 kuni05 1240 + evogen 1093):两者都是前向模拟规划器,但做**协同多步规划**——①开局对占领*集合+顺序*做分支定界搜索;②多源汇兵同时到达;③梯度式 supply chain 后方→前线;+双方在途台账、每回合多波次。我们复刻了模拟+价值内核,但单步贪心复刻不了*系统*。
</details>

---

*由 Claude Code agent 维护;状态表随讨论与天梯变化原地更新。*









