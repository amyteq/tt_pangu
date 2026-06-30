# ARC Prize 2026: ARC-AGI-3 深度研究报告  
## 兼论 ARC-AGI-2 与 ARC-AGI-3 的互相借鉴

**研究日期**: 2026-06-26（Australia/Melbourne）  
**面向读者**: 正在同时参与 ARC Prize 2026 ARC-AGI-2 与 ARC-AGI-3 的 Kaggle / agent 研发团队  
**结论摘要**: ARC-AGI-3 不是 ARC-AGI-2 的“下一版静态网格题”，而是从“看训练样例 -> 生成测试输出”的静态推理，转向“无语言说明 -> 交互探索 -> 建立世界模型 -> 发现目标 -> 规划行动”的在线 agent benchmark。两者共享对象分解、颜色/网格先验、DSL/程序归纳、MDL、候选生成与验证等底层技术，但 ARC-AGI-3 更强调探索、记忆、上下文压缩、动作效率、长期规划和抗过拟合。

---

## 1. Executive Summary

ARC-AGI-3 的核心区别是：**系统必须像玩家一样进入未知 2D grid game，在没有自然语言说明的情况下，通过交互发现规则与目标，并尽量用接近人类效率的动作数通关**。官方说明将其定位为第一个 interactive reasoning benchmark，强调 exploration、modeling、goal-setting、planning/execution 四项能力。

ARC-AGI-2 仍然是经典 ARC 风格：给定少量输入/输出训练样例，对测试输入生成最终 grid 输出，评分依赖 exact match。ARC-AGI-3 则要求每一步输出 action，并通过 RHAE（Relative Human Agent Efficiency）同时考察完成率和动作效率。换句话说：

- ARC-AGI-2 更像 “few-shot program synthesis / visual abstraction / static transformation inference”。
- ARC-AGI-3 更像 “embodied grid-world agent / active learning / hypothesis-driven exploration / online planning”。

对你的 KCA/Kaggle agent 项目来说，两者非常值得互相借鉴，但迁移方式应该是**共享底层 perception + DSL + hypothesis/refinement engine，而不是共享最终 submission 逻辑**。

---

## 2. ARC-AGI-3 比赛概览

### 2.1 目标

ARC-AGI-3 要求 agent 在没有说明、没有外部知识和没有联网的环境中玩一组 novel interactive games。每个 game 是 turn-based 2D grid world，agent 每步接收 frame/metadata，并选择一个动作。目标是完成关卡，并且动作数越接近或优于人类越好。

官方强调四类能力：

1. **Exploration**：主动探索未知环境，发现 affordances 与交互规律。
2. **Modeling**：建立可验证的世界模型，知道动作如何改变状态。
3. **Goal-setting**：从 feedback / progress / win condition 中推断目标。
4. **Planning and execution**：使用已学规则高效规划行动，避免无效动作。

### 2.2 奖金与时间线

ARC Prize 2026 官方页面显示三条赛道：ARC-AGI-3、ARC-AGI-2、Paper Prize。ARC-AGI-3 赛道总奖金为 **$850K**，其中 Grand Prize $700K，Top Score Prize $75K，另有 6 月 30 日与 9 月 30 日 milestone prizes。官方 ARC Prize 2026 总页面给出的全赛季关键日期包括 2026-03-25 开赛、2026-06-30 ARC-AGI-3 milestone #1、2026-09-30 milestone #2、2026-11-02 competition submission deadline、2026-12-04 results announced。

### 2.3 提交流程与限制

官方 starter kit 说明 ARC-AGI-3 提交通过 Kaggle Notebook 运行，Kaggle 会执行 Save & Run All 与 Competition Rerun 两次。代码入口主要是 `agent/my_agent.py` 中的 `MyAgent`，需要实现：

- `is_done(frames, latest_frame)`
- `choose_action(frames, latest_frame)`

Kaggle evaluation 禁用 internet。官方 starter docs 提到 Kaggle accelerators 包括 CPU/T4/P100/RTX6000，其中 RTX6000 reserved。Kaggle 竞赛规则页和官方 ARC 页面还要求获奖/领先方案 open-source，不能依赖外部 API 或 evaluation 时联网服务。

---

## 3. Data / Environment / Evaluation

### 3.1 数据集结构

ARC-AGI-3 论文和官方资料将环境分成三个层次：

| Split | 规模 | 用途 |
|---|---:|---|
| Public Demo | 25 games | 本地开发、demo、调试、公开可玩 |
| Semi-private | 55 games | 官方/平台 evaluation 的一部分 |
| Fully Private | 55 games | 隐藏最终测试，难度更高，更 OOD |

这点非常重要：**Public Demo 不应被当成真实性能的 validation set**。官方论文明确指出 public set 是 demonstration only，public scores 不代表真实泛化能力；public-to-private 的样本分布与 ARC-AGI-2 不同，private 集更大、更难、更 OOD。

Kaggle Data 页面搜索索引显示：公开游戏文件在 `environment_files` folder 中可用，公开游戏也可通过 arcprize.org 练习。

### 3.2 Game / frame / action format

官方 docs 说明 ARC-AGI-3 games 是 turn-based 2D grid environments。每个 observation 是 frame + metadata。常见约束：

- grid 最大约 64x64；
- cell value 在 0–15 color/channel 范围；
- 坐标以左上角为 `(0,0)`；
- action 通常包括 1–5 的 discrete actions，以及第 6 类带 `(x, y)` 坐标的 complex action；
- 每个 game 会通过 metadata 暴露可用动作，但 action 6 的 active coordinate affordance 未必直接给出。

论文进一步描述 action set 包括五个 key-like actions、Undo，以及带坐标 click 的 complex action。注意：agent 内部思考、工具调用、Python 计算不算 environment action；真正计分的是提交给环境的 action。

### 3.3 Scoring: RHAE

ARC-AGI-3 使用 RHAE（Relative Human Agent Efficiency）。它不是简单通关率，而是对每个 level 计算：

```text
level_score = (human_baseline_actions / ai_actions)^2
```

并做上限 cap。官方最新 scoring docs 和 2026-06 blog 明确将 human baseline 更新为 **upper median human**，单 level score cap 提高到 **1.15**。这与早期论文/早期描述中“second-best human score”不完全一致，参赛策略应该按最新官方 docs 实现。

聚合方式也很关键：game score 使用按 level index 加权的平均；只有通关所有 levels，才可能接近或达到 100% 解释下的完整 game success。后面的 level 权重大，意味着只打早期关卡、或者探索很多但不通关，收益会明显受限。

### 3.4 Human replay data

官方 human testing blog 提到 ARC-AGI-3 是 100% human-solvable；public 25 environments 有 342 条 human replay，145 条 solve replay。这个数据对 agent 非常有价值，但应该用于学习**通用探索策略、动作效率、progress 信号和行为模板**，而不是 memorizing public games 的 action sequence。

---

## 4. Code Page / Starter Kit / 本地开发建议

### 4.1 官方 starter kit

官方 starter kit 的开发路径大致是：

```bash
git clone https://github.com/arcprize/ARC-AGI-3-Kaggle-Starter.git
make setup
make play-local
make submit
make status
```

核心实现文件是：

```text
agent/my_agent.py
```

Starter random agent 可以作为 smoke test，但没有真正推理能力。建议从第一天就建立以下本地基础设施：

1. **Replay recorder / viewer**  
   保存每一步 frame、metadata、chosen action、state hash、delta、预测模型是否命中。

2. **Deterministic local evaluator**  
   固定 seed，多次运行同一个 game，区分 deterministic bug 与 stochastic variance。

3. **State graph database**  
   节点是 canonicalized frame/state，边是 action -> next_state / reward/progress。

4. **Failure bucket**  
   将失败分为 crash、timeout、invalid action、loop、goal-not-found、model-mismatch、planner-fail。

5. **Kaggle-safe packaging**  
   严格禁止联网，提前把所有权重、规则库、synthetic data、replay-derived priors 放进 dataset 或 notebook environment。

### 4.2 公开 notebooks / baselines

Kaggle Code 页面是 JS 渲染，公开索引能看到若干 relevant notebooks，例如：

- ARC3 Sample Submission / Stochastic Goose
- FORGE ARC-AGI-3 Simplified Baseline
- ARC3 Agent Evaluation and Recording Viewer

这些 notebooks 的价值主要不在最终分数，而在：

- 如何把 agent 包装成 Kaggle submission；
- 如何在本地与 Kaggle 环境之间保持一致；
- 如何记录 replay 与 scorecard；
- 如何减少 hidden evaluation crash。

建议优先复用 notebook 的 submission harness / evaluator / recording viewer，而不是直接复制策略逻辑。

---

## 5. Models Page / LLM 使用现实性

Kaggle Models 页面搜索索引显示有一些社区 model cards，例如 ModelBuddy、Cascading Cognition Engine 等。更重要的是官方 docs 提供了 LLM Agents 示例，包括标准 OpenAI-compatible API agent、ReasoningLLM、GuidedLLM 等模板。

但是要注意：

1. **Kaggle evaluation 禁止 internet**，所以 OpenAI/Anthropic/Gemini API agent 只能用于本地研究、prompt prototyping、human replay annotation，不能直接作为最终 Kaggle submission。
2. 官方 discussion 索引中有关于本地 open-weight Qwen offline 是否可用的问答，结论方向是：模型必须完整离线、evaluation 时不访问外部 API/internet。
3. LLM 在 ARC-AGI-3 中最适合扮演“hypothesis generator / rule explainer / planner critic”，而不是每一步在线调用一个大模型决策动作。原因是 runtime、context length、hidden crash、动作延迟和 offline packaging 都会成为风险。

可行架构是：

```text
Fast symbolic/perception core
  -> cheap exploration + state graph
  -> compact history summary
  -> optional offline local model proposes rules/plans
  -> symbolic simulator verifies
  -> planner executes with fallback
```

---

## 6. Discussion Page 重点信号

Kaggle Discussion 页面同样主要由 JS 渲染，但搜索索引显示了几个应高度关注的话题：

1. **Milestone prize deadline clarification**  
   说明阶段性奖励时间点与 eligibility 可能有细节，提交前必须再看规则。

2. **Daily submission limits correction**  
   官方曾修正 submission limit 说明。你的 KCA 自动化必须把 submission limit 作为 config，而不是写死。

3. **Persistent hidden test crashes: Heartbeats / Pydantic / submission code issues**  
   说明 hidden evaluation 的 engineering stability 是真实分数瓶颈。要做 watchdog、fallback、exception-safe choose_action。

4. **Score cap / human baseline clarification**  
   讨论中也出现 per-level cap 1.15、median human baseline 等细节，需按最新 docs 实现本地 scoring mirror。

5. **Offline open-weight model questions**  
   任何 LLM / local model 都必须满足 offline + packaged + reproducible。

---

## 7. 已公开研究与方法启发

### 7.1 Preview competition: informed search 很强

ARC-AGI-3 Preview Agent Competition 中，Tufa Labs 的 StochasticGoose 在 preview private 上达到 12.58%，Blind Squirrel 达到 6.71%。官方资料显示它们都偏向 informed search，而不是纯 LLM。这个信号很重要：

> 在未知 interactive game 中，强 baseline 往往来自 state graph + novelty exploration + action search，而不是端到端模型。

### 7.2 Executable World Models

Executable World Models 的研究方向是：让 coding agent 维护一个可执行 Python world model，并用它模拟/规划。在 public 25 games 上，v2 论文摘要报告 GPT-5.5 fully solved 15 games，mean RHAE 58.12%；GPT-5.4 solved 8 games，mean RHAE 41.29%。这说明“可执行世界模型 + 规划”是 ARC-AGI-3 的核心路线之一。但注意它报告的是 public games，private 泛化仍需验证。

### 7.3 AERA / Explore Before You Solve

AERA 类方法强调 Explore / Verify / Plan。论文摘要指出 public games 可以被一些非智能策略触达，因此 public set 容易误导；其 Qwen2.5-0.5B 方法 public RHAE 0.2116，另有 code track entry 在 full 55 private 上 RHAE 0.30。核心启发是：

- public game performance 不等于 intelligence；
- private 泛化需要规则发现与验证，而不是 memorized trajectories；
- 小模型 + structured exploration 可能比大模型 blind prompting 更稳。

### 7.4 Graph-Based Exploration

Graph-Based Exploration 使用 visual frame segmentation、salience-prioritized actions、state-transition graph 来做 training-free exploration，预览赛 private 排名靠前。这对你的实现非常直接：先搭一个强 state graph / object salience / novelty policy baseline，再加 LLM 或 DSL。

### 7.5 Map-then-Act Planning

Map-then-Act Planning 将问题分解为 global exploration、task-specific mapping、knowledge-augmented execution。它提醒我们不要急着让 agent “一边探索一边追求通关”，而是分阶段：

1. 快速建立地图/规则；
2. 识别目标与可达性；
3. 压缩成 plan；
4. 高效执行；
5. 失败时局部回滚/重规划。

---

## 8. 我建议的 ARC-AGI-3 技术路线

### 8.1 第一阶段：Kaggle-safe baseline + telemetry

目标不是立即高分，而是建立不会 crash、能复现、能分析失败的 submission。

必须实现：

- `safe_choose_action`: catch all exceptions，永远返回 valid action；
- metadata-aware valid action filtering；
- action repeat / loop detector；
- frame hash / canonical hash；
- delta visualization；
- local score mirror；
- replay dump + compact summary；
- time budget guard。

### 8.2 第二阶段：Object-centric perception

从每个 frame 提取：

- connected components；
- color histogram；
- bounding boxes；
- object size/shape/position；
- moving objects vs static objects；
- player-like object candidates；
- portals/doors/keys/targets/hazards candidates；
- changed cells after each action。

核心目标是把 64x64 color grid 变成 object/event stream：

```text
frame_t -> objects_t
action_t + objects_t -> objects_{t+1}, delta_t
```

### 8.3 第三阶段：State graph + exploration policy

构建 graph：

```text
Node = canonicalized observation / belief state
Edge = action -> next node, delta, progress, validity, cost
```

Action selection 可以按以下优先级：

1. 未尝试过的 valid action；
2. 对高 salience object 的 coordinate action；
3. 能产生最大 delta 的 action；
4. 能到达新 state 的 shortest path；
5. 若发现 progress/win signal，转入 exploit/planning；
6. 若进入 loop，重置策略或使用 undo/backtrack。

### 8.4 第四阶段：Hypothesis library / world model

维护一组可验证假设：

- movement model：哪个 object 是 player，动作方向如何映射；
- collision model：墙、可推、可穿、可拿；
- key-lock model：颜色/形状匹配；
- portal/teleport model；
- toggle/switch model；
- one-step transformation model；
- inventory/held-state model；
- hazard/death/restart model；
- reward/progress event model。

每个 hypothesis 都必须有：

```text
predict(state, action) -> predicted_state_delta
score(predicted_delta, observed_delta)
confidence update
```

规划只使用 confidence 高的模型。模型 mismatch 时立即 replan。

### 8.5 第五阶段：Planner

当模型可靠时，使用：

- BFS / A* for small state spaces；
- MCTS / rollout for uncertain models；
- macro-actions for repeated movement；
- shortest path to object/target；
- budget-aware plan truncation；
- online replanning after every action。

Scoring 是动作效率平方惩罚，所以一旦目标明确，应该快速从 exploration mode 切到 exploit mode。

### 8.6 第六阶段：Offline model / LLM augmentation

在 Kaggle runtime 允许的前提下，可以打包小型 open-weight model 或规则 transformer，但不要让它成为单点失败。适合的用法：

- 从 compact replay summary 中提出规则假设；
- 对 candidate plans 做 critique；
- 选择 hypothesis library 中的 prior；
- 生成 DSL rule snippets；
- 失败后分类原因。

不适合的用法：

- 每一步大模型自由输出 action；
- 依赖外部 API；
- 把 public game trajectory 直接 memorization；
- runtime 太长导致 Kaggle timeout。

---

## 9. ARC-AGI-3 主要挑战

### 9.1 无说明目标发现

ARC-AGI-2 的目标隐含在 train pairs 中；ARC-AGI-3 的目标可能只通过 progress / terminal / level transition 体现。agent 需要先探索，再猜测目标。

### 9.2 部分可观测与 context 管理

有些游戏可能要求记忆之前看到过的地图、object、sequence。论文也强调 context management 是核心挑战。不能把所有 frames 原样喂给模型，必须压缩为 structured memory。

### 9.3 动作效率

RHAE 使用 `(human_baseline / ai_actions)^2`，探索太久会被严重惩罚。探索策略必须区分：

- early cheap probes；
- high information gain actions；
- exploit mode；
- useless repeated actions。

### 9.4 Public overfitting

官方明确说 public set 是 demo，不是 leaderboard validation。过度针对 25 public games 写规则，会降低 private 泛化。

### 9.5 Hidden evaluation engineering

讨论区出现 hidden crash / heartbeat / Pydantic 等问题，说明很多分数损失并非算法，而是包装不稳。你的 KCA 框架应把 crash-free 作为 P0。

### 9.6 Offline/runtime constraints

无法联网，API LLM 不可用；大模型加载、推理时间、内存、依赖版本都可能成为风险。

---

## 10. ARC-AGI-2 与 ARC-AGI-3 能否互相借鉴？

结论：**能，但要迁移“中间层能力”，不是迁移最终策略。**

### 10.1 ARC-AGI-2 -> ARC-AGI-3

可迁移：

1. **Object segmentation**  
   ARC-AGI-2 中的 connected components、shape matching、color grouping、symmetry detection 可以直接用于 ARC-AGI-3 perception。

2. **DSL / program synthesis**  
   ARC-AGI-2 的 transform DSL 可以改造成 ARC-AGI-3 的 transition DSL，用于解释 `state_t + action -> state_{t+1}`。

3. **MDL / simplest explanation**  
   ARC 任务常需要选最简单规则。ARC-AGI-3 的 world model hypothesis 同样应按 simplicity + consistency 排序。

4. **Candidate generation + reranking**  
   ARC-AGI-2 中生成多个 candidate output 并验证；ARC-AGI-3 中可以生成多个 world model / plan 并用 observed transitions 验证。

5. **Synthetic data / TTT**  
   ARC-AGI-2 的 synthetic transformation tasks 可以转成小型 interactive episodes，训练 action-effect inference。

6. **Rule-class libraries**  
   颜色替换、形状复制、移动、对齐、填充、计数、路径等规则，在 ARC-AGI-3 中常体现为动态交互规则。

不可直接迁移：

- 直接 output grid 的 final decoder；
- 针对 ARC-AGI-2 train/test pair 的 prompt；
- 静态 exact-match search loop；
- 只会在一步生成答案、不会探索的 solver。

### 10.2 ARC-AGI-3 -> ARC-AGI-2

可迁移：

1. **Active hypothesis refinement**  
   虽然 ARC-AGI-2 没有环境可交互，但可以把 train examples 当成 observations，模拟 “hypothesis -> predict -> mismatch -> refine”。

2. **State/history compression**  
   ARC-AGI-3 中的 object/event summary 可帮助 ARC-AGI-2 做更稳健的 task abstraction。

3. **World model thinking**  
   ARC-AGI-2 多步 transformation 可以建模成 latent transition sequence，而不是一步 output。

4. **Planning/reranking**  
   对 ARC-AGI-2 候选程序做 step-by-step simulation 和 consistency checking，类似 ARC-AGI-3 planner 验证。

5. **Robustness engineering**  
   ARC-AGI-3 的 watchdog、fallback、crash-safe runtime 对 ARC-AGI-2 Kaggle submission 同样有价值。

不可直接迁移：

- Interactive action selection；
- action efficiency scoring；
- replay exploration；
- public game-specific state graph。

### 10.3 建议共享 repo 架构

```text
core/
  perception/
    components.py
    shape_features.py
    symmetry.py
    delta.py
  dsl/
    transforms.py
    predicates.py
    hypothesis.py
  search/
    beam.py
    mdl.py
    rerank.py
  eval/
    time_budget.py
    logging.py
    crash_guard.py

arc2/
  solver.py
  candidate_generation.py
  output_reranker.py
  kaggle_submission.py

arc3/
  agent.py
  state_graph.py
  exploration.py
  world_model.py
  planner.py
  replay_tools.py

synthetic/
  arc2_task_generator.py
  arc3_episode_generator.py
  transformation_to_game.py
```

这样你可以让 ARC-AGI-2 与 ARC-AGI-3 共用对象理解与规则归纳，但保持 submission-specific code 分离。

---

## 11. 提高成绩的具体技巧

### 11.1 Scoring-aware 技巧

- 不要无限探索；每个 level 设置 exploration budget。
- 对已发现规则的 level 立即切换到 shortest path / macro-action。
- 后期 level 权重更高，尽量不要只优化 level 1。
- 单 level cap 1.15，超人类 shortcut 的收益有限；更应追求稳定通关与少 crash。
- 记录每个动作是否带来 new state / useful delta，降低重复动作率。

### 11.2 Public-to-private 泛化技巧

- 用 public 25 games 验证 harness，不要把 public mechanics hard-code 到策略核心。
- 为每个 public game 做 leave-one-game-out validation。
- 自动生成 synthetic grid-worlds：keys/locks、maze、push block、teleport、toggle、collect all、avoid hazard、sequence memory。
- 对每类 synthetic game 做 ablation，观察 private-like 泛化能力。
- 分离 generic modules 与 per-game debug hacks，禁止 hacks 进入 final agent。

### 11.3 Engineering 技巧

- `choose_action` 必须 exception-safe。
- 所有 numpy/pydantic/dependency 版本在 Kaggle notebook 中 smoke test。
- 设置 global deadline，例如每步最多 X ms，超时 fallback。
- 不要保存过大 replay 到 Kaggle output，避免 IO 爆炸。
- 用 integer encoding 和 numpy diff 加速 frame delta。
- 所有 stochastic policy 固定 seed，并可配置多 seed ensemble。
- hidden evaluation 前做 “no internet / clean env / no local absolute path” 测试。

### 11.4 Analysis loop 技巧

每次提交后整理：

| Bucket | 需要记录 |
|---|---|
| solved levels | game, level, action_count, human_baseline_ratio |
| failed but progressed | max_level, progress event, stuck state |
| invalid action | action type, metadata, coordinates |
| loop | repeated state hash cycle |
| crash | traceback, dependency, frame metadata |
| model mismatch | predicted delta vs observed delta |
| timeout | step count, wall time, model call count |

你的 KCA 自动化可以把这些 bucket 变成 nightly regression report。

---

## 12. 我给你的研发优先级建议

如果你同时做 ARC-AGI-2 与 ARC-AGI-3，建议按下面分配：

### ARC-AGI-3 优先级

1. **P0: Stable submission harness**  
   不 crash、不 timeout、valid action、local/Kaggle 一致。

2. **P1: Replay/state graph/perception**  
   这是后续所有智能的基础。

3. **P2: Generic exploration policy**  
   novelty + salience + action-effect learning。

4. **P3: Hypothesis/world model + planner**  
   先覆盖 movement/collision/key-lock/portal/toggle/collect/avoid hazard。

5. **P4: Offline model augmentation**  
   小模型用于 rule suggestion，不做每步端到端决策。

### ARC-AGI-2 优先级

1. **DSL + neural candidate ensemble**
2. **Object-centric abstraction**
3. **TTT / synthetic data**
4. **Candidate reranking and verifier**
5. **Strict time budget and exact-match fallback**

### 共享投入

- `core/perception` 与 `core/dsl` 是最值得共享的。
- `core/search/mdl.py` 与 `core/eval/time_budget.py` 也应共享。
- 避免把 ARC-AGI-3 public game hacks 污染 ARC-AGI-2 solver。

---

## 13. 可执行的 Claude Code / KCA Task Prompt 建议

下面是一份可以给 Claude Code plan mode 的英文 prompt 草案：

```md
# Goal: Build an ARC-AGI-3 baseline agent architecture with reusable ARC core modules

You are working in the Kaggle competition repo for ARC Prize 2026. Implement a stable, Kaggle-safe ARC-AGI-3 baseline and shared ARC core utilities that can later be reused by ARC-AGI-2.

Hard constraints:
- Do not use internet or external APIs at runtime.
- Keep the agent deterministic by default.
- `choose_action` must never crash; all errors must fall back to a valid action.
- Do not hard-code public game IDs or game-specific action sequences.
- Keep modules small and testable.

Deliverables:
1. `core/perception/`
   - frame canonicalization
   - connected component extraction
   - color histogram and shape features
   - frame delta and changed-cell summaries
2. `arc3/state_graph.py`
   - state hash
   - node/edge memory
   - loop detection
   - action outcome statistics
3. `arc3/exploration.py`
   - valid-action filtering
   - novelty-based exploration
   - salience-based coordinate-action proposal
   - budget-aware fallback
4. `arc3/world_model.py`
   - simple transition hypotheses for movement/collision/toggle/key-lock/portal/collect
   - confidence update using observed deltas
5. `arc3/planner.py`
   - BFS/A* over trusted model when available
   - online replanning on mismatch
6. `agent/my_agent.py`
   - integrate the above into the Kaggle starter interface
   - exception-safe `is_done` and `choose_action`
7. Tests
   - unit tests for perception/delta/state graph
   - no-internet smoke test
   - deterministic replay test
8. Documentation
   - `docs/arc3_agent_architecture.md`
   - `docs/arc2_arc3_shared_core.md`
   - `docs/regression_checklist.md`

Start by auditing the current repo layout and starter API. Then propose a concise plan before editing code.
```

---

## 14. Open questions / 需要赛前持续跟踪

1. Kaggle daily submission limit 是否再次调整。
2. Milestone prize eligibility 是否有额外 open-source timing 要求。
3. RTX6000 reserved / accelerator availability 是否稳定。
4. Hidden evaluation crash 的 common causes 是否有新的 discussion fix。
5. 官方 scoring docs 是否继续调整 human baseline 或 cap。
6. Public notebooks 是否出现新的 strong open-source baseline。
7. 是否有可合法打包的 small offline VLM/LLM 能在 Kaggle runtime 内稳定运行。
8. ARC-AGI-2 / ARC-AGI-3 是否可共享 synthetic data 而不违反 competition rules。

---

## 15. 最终建议

对 ARC-AGI-3，不要从“大模型端到端玩游戏”开始。更稳的路线是：

```text
crash-safe harness
-> replay/state graph
-> object-centric perception
-> novelty/salience exploration
-> hypothesis library
-> verified world model
-> efficient planner
-> optional offline model augmentation
```

对 ARC-AGI-2，不要因为 ARC-AGI-3 变成 interactive 就放弃已有 ARC solver 技术。ARC-AGI-2 的 object abstraction、DSL、candidate verifier、synthetic TTT，恰好是 ARC-AGI-3 world model 的底层材料。

最终最值得投入的是一个共享的 **ARC Core Reasoning Library**：  
它不直接属于 ARC-AGI-2 或 ARC-AGI-3，而是服务于两者的 object perception、rule induction、hypothesis refinement、simulation and verification。

---

## 16. Source Notes

Primary sources used:

- ARC Prize 2026 official ARC-AGI-3 competition page  
  https://arcprize.org/competitions/2026/arc-agi-3/
- ARC Prize official ARC-AGI-3 info page  
  https://arcprize.org/arc-agi/3/
- ARC Prize 2026 overview  
  https://arcprize.org/competitions/2026/
- ARC Prize official ARC-AGI-2 competition page  
  https://arcprize.org/competitions/2026/arc-agi-2/
- ARC-AGI-3 docs starter kit  
  https://docs.arcprize.org/arc-agi-3/for-competitors/getting-started
- ARC-AGI-3 docs games  
  https://docs.arcprize.org/arc-agi-3/concepts/games
- ARC-AGI-3 docs actions  
  https://docs.arcprize.org/arc-agi-3/concepts/actions
- ARC-AGI-3 docs scoring  
  https://docs.arcprize.org/arc-agi-3/key-concepts/scoring
- ARC Prize blog: ARC-AGI-3 benchmark updates  
  https://arcprize.org/blog/arc-agi-3-benchmark-updates
- ARC Prize blog: Human testing and replay dataset  
  https://arcprize.org/blog/arc-agi-3-human-testing
- ARC-AGI-3 technical paper / arXiv  
  https://arxiv.org/abs/2606.05731
- ARC-AGI toolkit GitHub  
  https://github.com/arcprize/arc-agi
- ARC-AGI-3 agents GitHub  
  https://github.com/arcprize/ARC-AGI-3-Agents
- ARC-AGI-3 benchmarking GitHub  
  https://github.com/arcprize/arc-agi-3-benchmarking
- Executable World Models for ARC-AGI-3  
  https://arxiv.org/abs/2606.18238
- Explore Before You Solve / AERA  
  https://arxiv.org/abs/2606.14077
- Graph-Based Exploration for ARC-AGI-3  
  https://arxiv.org/abs/2606.10633
- Map-then-Act Planning for ARC-AGI-3  
  https://arxiv.org/abs/2606.10103
- ARC Prize 2025 technical report  
  https://arxiv.org/abs/2606.07364
- ARC-AGI-2 paper  
  https://arxiv.org/abs/2604.18405

Limitations:
- Kaggle Overview/Data/Code/Models/Discussion pages are partly JS-rendered and may require login/session rendering. I used official ARC Prize pages, official docs, GitHub repos, arXiv papers, and Kaggle search/index snippets for auditable facts. Before final submission decisions, re-check the live Kaggle pages directly in a browser logged into the competition.
