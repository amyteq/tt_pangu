# Orbit Wars — ChatGPT 独立分析与计划 (A2, 2026-06-11)

> 来源: ChatGPT 对同一问题的独立回答(含模块化 agent 架构、实验路线 v0-v6、评估纪律)。
> 供 issue #87 引用;注意其 'PyTorch 不可用' 的说法已被我们实证推翻(torch 版 kuni05 上 ladder ~1137)。

# Q2:
请给我详细介绍一下 [Orbit Wars](https://www.kaggle.com/competitions/orbit-wars/overview) 这个比赛，你的ideas，你认为存在的挑战，以及可以提高成绩的技术和技巧!

# A2:
下面我按“比赛机制 → 我会怎么做 → 主要挑战 → 提分技术与实验路线”来讲。**截至 2026-06-11**，它仍是一个正在进行中的 Kaggle 仿真对战赛；第三方聚合页列出的赛程是 2026-04-16 开始、2026-07-08 结束，奖金池 $50,000，Kaggle 官方搜索片段也标明目标是创建/训练 AI bots 来玩一个 1v1 或 4p FFA 多智能体游戏。([AI Competition Hub][1])

## 1. Orbit Wars 是什么比赛？

**Orbit Wars 本质上不是传统 ML 表格赛，而是 Kaggle Environments 的多智能体 bot 对战赛。**你提交的是一个 agent/bot，它每回合根据观测返回一组动作，和其他参赛者的 bot 在环境里反复对战。官方环境 README 描述它是一个 2 人或 4 人实时策略游戏：在 100×100 连续二维空间中，玩家从一个 home planet 出发，通过发射舰队占领中立或敌方星球；星球会围绕中心太阳运动，彗星会沿椭圆轨道穿过棋盘，游戏默认持续 500 回合，最后拥有最多总 ships 的玩家获胜。([GitHub][2])

游戏地图不是格子，而是**连续坐标空间**：棋盘中心有半径 10 的太阳，舰队路径穿过太阳会被摧毁；所有星球和彗星按中心四重镜像/旋转对称布置，以保证不同起始位置公平。星球记录格式是 `[id, owner, x, y, radius, ships, production]`，production 为 1–5，拥有者每回合按 production 增加 ships；星球半径与 production 相关，高产星球通常更大、更容易碰撞。([GitHub][2])

每个舰队格式是 `[id, owner, x, y, angle, from_planet_id, ships]`。你的动作格式是一个列表：`[[from_planet_id, direction_angle, num_ships], ...]`，也就是从某个自有星球按某个角度发射若干 ships；同一回合可以从多个星球、甚至同一星球发射多支舰队。([GitHub][2])

一个非常关键的机制是**舰队速度随规模增加**：官方 README 给出的速度公式是 `speed = 1.0 + (maxSpeed - 1.0) * (log(ships) / log(1000)) ^ 1.5`，默认 `maxSpeed=6.0`；1 ship 每回合约走 1 单位，约 500 ships 能接近 5，约 1000 ships 接近最大速度。这个机制让“多发小船”和“少发大船”的战略完全不同：大舰队不仅战斗力强，而且更快。([GitHub][2])

彗星是临时星球，会在第 50、150、250、350、450 回合附近成组出现，每组四个、每象限一个；它们有固定半径 1、production 1，也可以被占领、产船、发射舰队，但离开棋盘时会被移除，驻扎在上面的 ships 也会消失。官方 observation 中包含 `comets`、`paths` 和 `path_index`，所以在彗星出现后可以预测其未来轨迹。([GitHub][2])

回合顺序也很重要：先处理彗星过期和生成，再处理所有玩家发射舰队，然后星球产船、舰队移动、星球/彗星移动，最后结算战斗。战斗结算不是简单的“先到先打”，而是把同一星球的到达舰队按 owner 汇总，最大攻击方先和第二大攻击方互相抵消，剩余力量再和星球驻军结算；如果最大攻击力量并列，则攻击方全灭。([GitHub][2])

评分上，游戏到 500 回合或只剩一个/零个玩家有星球或舰队时结束，最终分数是“自有星球上的 ships + 自有舰队中的 ships”，最高者获胜。也就是说，最后阶段不是盲目扩张，而是要问：这次发射是否会增加最终 ships，还是只是把安全驻军送去太阳、边界或无效目标。([GitHub][2])

## 2. 评测与提交机制：为什么不能只看一次 LB？

Orbit Wars 是 ladder 式仿真赛。Kaggle/镜像信息显示：每队每天最多提交 5 个 agents；提交会和 skill rating 相近的 bot 打 episodes，赢则评分上升，输则下降；为了减少池中 bot 数量并提高每个 team 的有效对局量，最终只跟踪最新 2 个 submission；Leaderboard 上通常展示你最好 scoring bot。([AI Competition Hub][1])

这意味着它的 Public LB 像“竞技天梯”，不是固定测试集分数。一个 bot 刚提交时可能对局不足，rating 方差大；某个版本短期升分可能只是匹配噪声或碰到了弱对手。我的建议是：**本地胜率和稳定性优先，LB 只作为延迟、噪声较大的外部验证**。

环境配置方面，官方 spec 显示 `orbit_wars` 当前版本为 `1.0.9`，默认 `episodeSteps=500`，`actTimeout=1` 秒，`shipSpeed=6.0`，`cometSpeed=4.0`，observation 里有 `remainingOverageTime=60`。所以线上 bot 必须足够快，不能每回合做很重的搜索或神经网络推断。([GitHub][3])

## 3. 我对这个比赛的总体思路

我会把它看成三个层次：

第一层是**几何与规则引擎**。你必须能准确预测星球位置、彗星位置、舰队 ETA、路径是否撞太阳、是否出界、是否会碰到移动星球。这个层次没做好，后面的 RL 或高级策略都会被错误动作拖垮。

第二层是**强启发式策略**。Orbit Wars 的动作空间很大，但不是所有动作都有意义。大多数有效动作都是“从某个自有星球，打某个中立/敌方/待防守目标，发一个经过计算的 ships 数量”。先做一个强 heuristic bot，通常比一开始上 PPO/AlphaZero 更实际。

第三层才是**学习与搜索增强**。可以用 replay imitation、自博弈、离线 RL、进化调参、beam search/MCTS 等方法，但线上最好蒸馏成小模型或纯 Python/numpy 逻辑。社区讨论中有参赛者报告 Orbit Wars 评估环境里 PyTorch 不可用，所以深度模型线上推断要非常谨慎，最好准备 numpy/纯 Python fallback。([Kaggle][4])

## 4. 具体 ideas：我会优先做哪些策略模块？

### A. 几何预测核心：先把“能不能打中”做准

Orbiting planets 可以用 `initial_planets` 和 `angular_velocity` 预测位置；官方 README 明确提到 observation 中给出了这两个字段。([GitHub][2]) 我的做法是建立几个函数：

`planet_pos(pid, t)`：预测第 t 回合某星球位置。
`fleet_speed(ships)`：复现官方速度公式。
`eta(source, target, ships, now)`：迭代求舰队发射后多久能碰到目标。
`safe_path(source_pos, angle, speed, eta)`：检查路径是否穿太阳、出界或撞到非目标。
`required_ships(target, eta)`：估计到达时需要多少 ships 才能占领或守住。

最核心的技巧是：不要只朝目标当前坐标打。对 orbiting planet 和 comet，要朝“未来位置”打。可以枚举 ETA，比如 1–80 回合，预测目标在 `now+eta` 的位置，然后反推角度与距离，再检查 `distance / fleet_speed(ships)` 是否接近 eta。

### B. 早期扩张：ROI，而不是最近优先

Starter agent 会找最近的 static 非自有星球发射半数 ships，这是合理 baseline，但远远不够。官方 starter agent 的逻辑就是找最近 static target 并在 ships 足够时发射，这说明 baseline 很简单。([GitHub][5])

更强的扩张应计算 ROI：

`value = production * remaining_turns - capture_cost - travel_risk - defense_cost`

早期优先高 production、低驻军、距离近、路径安全、且不容易被敌人反抢的星球。低产远点即使能占，也可能在回本前游戏就进入中后期。

### C. 防守账本：每个星球都要算未来安全余量

很多 bot 会输在过度扩张：把 home planet 或高产核心星球抽空，导致敌方一波反推。我的做法是为每个自有星球维护一个“未来时间轴”：

当前驻军 + 未来 production + 已知我方援军 - 已知敌方来袭 - 计划发出的 ships

如果未来某个 t 变成负数，就触发防守动作：从最近可支援星球发援军，或取消计划中的进攻。这个 defense ledger 比单纯“每个星球保留 20% ships”强很多。

### D. 同步多源攻击：不是单点乱射

Orbit Wars 的战斗会把同一星球同一回合附近到达的舰队汇总结算；最大攻击方和第二大攻击方先互相抵消，这使多源同步攻击非常有价值。([GitHub][2])

做法是：选一个目标，枚举到达时间 T，让多个自有星球发不同数量的 ships，使它们在 T 附近同时到达。这样可以避免单支舰队太早到达被消耗，也可以减少过量发兵。同步攻击尤其适合打敌方高产核心、彗星争夺、或 4p 中的关键中立点。

### E. 舰队规模分桶：利用“大舰队更快”

速度随 ships 对数增加，这会导致一个反直觉现象：有时发 80 ships 不如发 150 ships，因为后者更快到达、能少吃几回合敌方 production。([GitHub][2])

我会把发兵量限制在少数候选分桶：`min_needed * {1.0, 1.1, 1.25, 1.5}`，再加一些速度阈值附近的 ship 数，比如能显著缩短 ETA 的点。这样既减少动作空间，又能利用速度曲线。

### F. 彗星策略：只抢“能回本且不会过期”的彗星

彗星会在固定阶段出现，并且离开棋盘时驻军会消失。([GitHub][2]) 所以彗星不是见到就抢。我的规则会是：

如果彗星剩余可见时间短，不抢；
如果抢完后能发起二次攻击，价值上升；
如果敌人也能轻松抢，必须算同步攻击/防守成本；
如果彗星路径靠近我方核心，可当临时跳板；
如果需要大量 ships 才能抢，且 production 只有 1，通常不值得。

### G. 2p 与 4p 分开写策略

2p 接近零和博弈：压制对手、抢高产、打断扩张都很重要。
4p 是 FFA：过早和一个敌人两败俱伤，常常让第三方得利。Kaggle 官方目标包含 1v1 或 4p FFA。([Kaggle][6])

4p 下我会加入“kingmaker/third-party risk”分数：如果某次进攻会让自己和目标都损失大量 ships，而旁边第三方没有损失，就降低该动作优先级。4p 更强调稳健扩张、守住高产星球、避免单线 all-in。

### H. Replay mining / imitation heuristic

Kaggle 已经有 Orbit Wars episode replay 数据集和社区整理的 parquet/replay 工具，例如官方日度 episode dataset、parquet replay 讨论、top-player replay EDA 等。([Kaggle][7])

可以从高分 replay 中提取：什么时候扩张、打哪些星球、发兵比例、保留多少驻军、什么时候放弃彗星、什么时候多源同步。即使不训练神经网络，也可以把这些统计变成 heuristic 参数。

### I. RL：可以做，但不要一开始就押宝

RL 可行路线是：离线用 PyTorch/JAX 训练，线上蒸馏成小型 numpy policy。状态编码建议用 planet/fleet/comet 的 set encoder，例如 DeepSets、attention 或轻量 Transformer；动作不要直接输出连续角度，而是输出：

source planet pointer
target object pointer
ship fraction / ship bucket
mode：expand / attack / defend / reinforce / comet

这样动作空间会小很多。直接让 RL 输出任意 `[planet_id, angle, ships]` 通常太难学。

## 5. 我认为最大的挑战

**第一，连续几何难。**它不是 grid RTS，发射角度、移动目标、太阳遮挡、边界、星球半径、舰队速度都影响结果。官方环境使用连续碰撞检测，检查舰队路径段是否碰到星球，而不只是检查终点。([GitHub][2])

**第二，动作效果延迟很长。**你现在发出的舰队可能几十回合后才到；到达时目标的 owner、ships、位置都可能变了。强 bot 必须能做中期预测，而不是只看当前局面。

**第三，发兵量和 ETA 耦合。**ships 越多速度越快，所以“需要多少 ships 才能占领”不是简单的目标驻军 + production × 时间，因为时间本身又取决于 ships。这个要迭代求解。

**第四，防守比进攻更容易被低估。**占一个星球只是第一步，守到它回本才是收益。很多复杂策略会因为抽空核心星球而输给简单稳健 bot。

**第五，4p 的非零和性。**你打 A，B 可能获利；你救某个边缘星球，可能只是帮另一个玩家挡刀。4p 里“局部最优战斗”经常是全局坏动作。

**第六，Leaderboard 噪声大。**天梯评分需要足够 episode 才稳定。每天 5 次提交、最终最新 2 个 submission 的机制意味着提交管理本身也是策略。([AI Competition Hub][1])

**第七，运行时限制。**官方 spec 默认每回合 `actTimeout=1` 秒，`remainingOverageTime=60`，所以代码要快、稳定、无重依赖。([GitHub][3])

**第八，环境细节和版本变化。**Kaggle environments repo 里 Orbit Wars 目录包含 README、JSON spec、Python interpreter、测试文件；GitHub issues 中也出现过关于 OOB、彗星过期、碰撞顺序等边界逻辑的讨论。实战中必须锁定本地环境版本，并用 replay/单元测试验证自己的模拟器。([GitHub][2])

## 6. 提高成绩的技术和技巧

### 1）本地 arena 比 LB 更重要

搭一个本地 tournament harness：你的 v1/v2/v3/v4 互相对打，再加 starter/random/open-source bots。每次改动跑成百上千局，按 2p/4p、不同 seeds、不同地图类型分组统计胜率。Kaggle Environments 支持本地 `make`、`run`、`evaluate` 这类 episode 评估流程。([GitHub][8])

不要只看总体胜率。至少记录：

2p 胜率、4p 胜率；
平均最终 ships；
早期扩张数量；
核心星球丢失次数；
无效舰队比例：撞太阳、出界、打空、过量发兵；
每回合平均耗时、p95 耗时。

### 2）做 paired-seed A/B test

同一批 seeds 下 vA 和 vB 都打一遍，这比随机打若干局更能减少地图差异造成的噪声。一个改动如果只提升 20 局表现，不可信；如果在 500+ paired episodes 上稳定提升，才值得提交。

### 3）建立“战术事件日志”

每回合记录 bot 做决策的理由，例如：

`EXPAND p3 -> p12 ships=37 eta=9 roi=82`
`DEFEND p5 threat=61 reserve=20 send=45 from p2`
`SKIP_ATTACK target p9 third_party_risk=0.72`
`COMET_SKIP expires_in=8 payback=31`

这样看 replay 时能知道 bot 为什么输，而不是只看到舰队乱飞。

### 4）动作候选剪枝

每回合不要枚举所有角度。候选动作可以来自：

最近/最高 ROI 的 N 个 neutral planets；
敌方高 production 星球；
受威胁自有星球；
当前可见 comet；
能同步到达的多源攻击目标；
endgame 中能改变最终 score 的目标。

每个 source planet 只保留前 K 个候选 target，每个 target 只试少数 ship buckets。这样能在 1 秒内做更深的评估。

### 5）保守发兵是强 baseline

经验上，强启发式 bot 的关键不是“更聪明地 all-in”，而是“少犯灾难性错误”。建议所有进攻都加约束：

核心星球不能低于动态 reserve；
高 production 星球 reserve 更高；
敌方舰队在途时禁止抽空；
早期限制远距离攻击；
打高风险目标时要求 1.15–1.35 的 surplus；
4p 下提高 garrison buffer。

### 6）用 forward simulation 给候选动作打分

每回合可以构造 20–100 个候选 action set，用简化模拟往前滚 20–60 回合。对手模型可以先用简单 heuristic：扩张、最近攻击、威胁防守。评分函数可以是：

`score = my_total_ships - max_enemy_total_ships + α*my_production - β*frontier_risk + γ*safe_planets + δ*comet_value`

不要追求完全精准，重点是让 bot 避免显然坏的动作。

### 7）分阶段策略

早期 0–80：优先低成本高 ROI 静态星球，少打长途；保 home。
中期 80–300：建立前线，防守账本，争夺高产星球和关键彗星。
后期 300–450：减少回本周期过长的扩张，更多看最终 score swing。
终局 450–500：只做能改变最终分数/控制权的动作；避免无意义舰队撞边界或太阳。

### 8）针对 fleet speed 做“发兵求解器”

对每个目标，用迭代法求最小 ships：

先估一个 ETA；
用 ETA 预测目标 ships；
计算需要 ships = 目标驻军 + 安全 margin；
用该 ships 反算速度和新 ETA；
重复直到稳定；
再试 1.1×、1.25× 等 surplus 版本。

这会明显优于固定发半数 ships。

### 9）Replay imitation 不一定要训练大模型

可以从 top replay 中统计一些可解释规则：

不同阶段平均 reserve ratio；
高分 bot 攻击 neutral 的 ROI 阈值；
攻敌时 surplus 分布；
comet 参与率；
多源同步频率；
4p 中对最近敌/最强敌/最高分敌的攻击倾向。

然后把这些变成参数，使用 Optuna/CMA-ES/遗传算法在本地 arena 里调参。

### 10）线上提交管理

因为每天最多 5 次、最终最新 2 个 submissions 重要，我会保留两个分支：

`stable`: 本地大样本验证过的稳健版本；
`experimental`: 新策略版本，小心提交观察。

不要在最后阶段连续提交未经验证的版本，避免最新 2 个都变差。提交前至少跑：starter/random、自家历史强版本、若干开源 bot、本地 2p/4p 混合 tournament。

## 7. 一个我认为很有竞争力的 agent 架构

我会设计成以下模块：

`StateParser`：把 planets/fleets/comets 转成 typed objects，缓存自有、中立、敌方对象。
`GeometryEngine`：预测星球/彗星位置、ETA、路径安全、碰撞风险。
`ThreatLedger`：计算未来 1–80 回合每个自有星球的安全余量。
`CandidateGenerator`：生成扩张、防守、攻击、彗星、同步进攻候选。
`ActionEvaluator`：用 ROI + forward simulation + 风险惩罚打分。
`Scheduler`：避免多个动作重复使用同一批 ships，确保 reserve 不被突破。
`MetaPolicy`：按阶段、2p/4p、领先/落后状态调整激进程度。
`Logger`：输出本地 debug reason，线上关闭。

核心伪逻辑大概是：

```text
parse observation
update predicted positions and incoming fleet ledger
reserve ships for threatened planets
generate mandatory defense actions
generate expansion / attack / comet candidates
group candidates by source ships budget
score candidates with ROI + short rollout
select non-conflicting actions under reserve constraints
return actions
```

这个框架先不用神经网络也能很强；后续如果做学习，可以让模型只参与 candidate scoring，而不是直接生成任意角度动作。

## 8. 我会如何安排实验路线

**v0：规则复现与 baseline。**先复现 speed、ETA、orbit prediction、sun/OOB check，跑 starter/random，确保动作格式合法且耗时稳定。

**v1：强扩张 bot。**ROI 选点、动态 reserve、只打 static 或容易预测的目标。目标是稳定打赢 starter。

**v2：防守账本 + 反击。**加入 incoming fleet 预测、支援、取消危险进攻。目标是减少“占了很多星球但核心被偷”的失败。

**v3：同步攻击 + 2p/4p 分策。**加入多源 wave attack、4p 风险惩罚、领先/落后模式。

**v4：comet 策略 + endgame 策略。**只抢能回本的彗星，终局只做 score-positive 动作。

**v5：replay mining / 参数优化。**用高分 replay 统计行为，用本地自博弈调参数。

**v6：轻量学习增强。**如果时间够，再做 imitation/RL，并蒸馏成 numpy 小模型；线上仍保留 heuristic fallback。

## 9. 最重要的提分优先级

我的优先级会是：

1. **精确几何 + ETA**：打不中，一切归零。
2. **动态防守 reserve**：少输灾难局。
3. **ROI 扩张**：早期雪球来源。
4. **同步攻击**：中后期突破强敌。
5. **2p/4p 分策略**：避免 FFA 里帮别人打工。
6. **本地大样本验证**：不要被 LB 噪声牵着走。
7. **轻量、可解释、快速的线上代码**：1 秒回合限制下，稳定比花哨更值钱。

一句话总结：**Orbit Wars 的胜负核心不是单纯“上 RL”，而是把连续几何、资源回本、防守余量和多源时序进攻做稳。先做一个极强、极保守、极少犯错的 heuristic bot，再用 replay/RL/search 去增强候选评分，才是我认为最靠谱的冲分路线。**

[1]: https://www.competehub.dev/en/competitions/kaggleorbit-wars?utm_source=chatgpt.com "Orbit Wars - CompeteHub | Machine Learning Competition Compe"
[2]: https://github.com/Kaggle/kaggle-environments/tree/master/kaggle_environments/envs/orbit_wars "kaggle-environments/kaggle_environments/envs/orbit_wars at master · Kaggle/kaggle-environments · GitHub"
[3]: https://github.com/Kaggle/kaggle-environments/raw/refs/heads/master/kaggle_environments/envs/orbit_wars/orbit_wars.json "raw.githubusercontent.com"
[4]: https://www.kaggle.com/competitions/orbit-wars/discussion/694071?utm_source=chatgpt.com "PyTorch is not available in the Orbit Wars evaluation environment"
[5]: https://github.com/Kaggle/kaggle-environments/raw/refs/heads/master/kaggle_environments/envs/orbit_wars/orbit_wars.py "raw.githubusercontent.com"
[6]: https://www.kaggle.com/competitions/orbit-wars?utm_source=chatgpt.com "Orbit Wars"
[7]: https://www.kaggle.com/datasets/kaggle/orbit-wars-episodes-2026-06-08?utm_source=chatgpt.com "Orbit Wars Episodes 2026-06-08"
[8]: https://github.com/kaggle/kaggle-environments "GitHub - Kaggle/kaggle-environments · GitHub"
