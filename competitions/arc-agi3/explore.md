# Q1
详细阅读了解[ARC Prize 2026 - ARC-AGI-3](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3) 这个比赛, 深入Overview, Data, Code, Models, Discussion 等pages 并做全面的研究, 向我做详细介绍, 并给出你的ideas, 你认为存在的挑战, 以及可以提高成绩的技术和技巧! 我也在做 [ARC Prize 2026 - ARC-AGI-2](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2) 这个比赛, 这两个比赛可否互相借鉴? 最后提供分析文件的下载链接!

# A1
已完成 ARC-AGI-3 的研究梳理，并把完整分析报告生成好了：

* [下载 Markdown 分析报告](sandbox:/mnt/data/arc_agi3_arc_agi2_research_report_zh_20260626.md)
* [下载 ZIP 打包文件](sandbox:/mnt/data/arc_agi3_arc_agi2_research_report_zh_20260626.zip)

## 核心结论

**ARC-AGI-3 不是 ARC-AGI-2 的简单升级版，而是从“静态 grid 推理”转向“交互式 agent 推理”。** ARC-AGI-2 的任务是根据少量 input/output examples 生成测试 grid，评分看 exact match；ARC-AGI-3 则要求 agent 在没有语言说明的 2D grid game 中探索、建模、发现目标并高效行动，官方强调 exploration、modeling、goal-setting、planning/execution 四类能力。([ARC Prize][1])

ARC-AGI-3 的评分是 **RHAE**，同时考察是否完成和动作效率。最新官方 scoring docs 使用 **upper median human** 作为 human baseline，并将单 level score cap 设为 **1.15**；这意味着“通关 + 少走弯路”比单纯探索更重要。([docs.arcprize.org][2])

ARC-AGI-3 的数据层次也很关键：public demo 有 25 games，semi-private 和 fully-private 各 55 games；官方论文明确提醒 public set 主要用于 demonstration/debug，不应当作为真实泛化能力的 validation。([arXiv][3])

## 我认为最有前途的 ARC-AGI-3 路线

不要从“端到端 LLM 玩游戏”开始。更稳的架构是：

```text
crash-safe Kaggle harness
-> replay recorder / state graph
-> object-centric perception
-> novelty + salience exploration
-> hypothesis library / executable world model
-> planner with replanning
-> optional offline local model augmentation
```

公开研究也支持这个方向。Preview competition 中较强方案偏向 informed search；近期论文中 executable world models、graph-based exploration、map-then-act planning 都说明 ARC-AGI-3 的关键不是单步猜动作，而是探索、建图、归纳规则、验证模型和规划。([ARC Prize][4])

## ARC-AGI-2 与 ARC-AGI-3 能否互相借鉴？

**可以，而且很值得，但应共享“中间层能力”，不要共享最终 submission 逻辑。**

ARC-AGI-2 可以迁移到 ARC-AGI-3 的部分包括：

* connected components、shape matching、color grouping、symmetry detection；
* DSL / program synthesis；
* candidate generation + verifier；
* MDL / simplest consistent explanation；
* synthetic transformation data；
* TTT / reranking / ensemble 思路。

ARC-AGI-3 可以反向帮助 ARC-AGI-2 的部分包括：

* active hypothesis refinement；
* object/event memory compression；
* multi-step transformation as latent planning；
* stronger verifier / replay simulator；
* crash-safe Kaggle engineering。

我建议你把两个比赛的 repo 逐步抽成共享核心：

```text
core/
  perception/
  dsl/
  search/
  eval/

arc2/
  solver.py
  candidate_generation.py
  output_reranker.py

arc3/
  agent.py
  state_graph.py
  exploration.py
  world_model.py
  planner.py
```

这样 ARC-AGI-2 与 ARC-AGI-3 可以共享底层 object abstraction、DSL、hypothesis search 和 evaluation utilities，但各自保留独立 submission layer。

## 需要特别注意

Kaggle 的 Code / Models / Discussion 页面有较多 JS 渲染内容，我能核对到官方 ARC docs、GitHub、arXiv、Kaggle 搜索索引和公开页面信息；正式提交前，建议你再用登录后的浏览器检查 live Kaggle Discussion，尤其是 submission limit、milestone eligibility、hidden crash workaround、offline model packaging 这些可能变化的细节。

[1]: https://arcprize.org/arc-agi/3 "ARC-AGI-3"
[2]: https://docs.arcprize.org/methodology "ARC-AGI-3 Scoring Methodology - ARC-AGI-3 Docs"
[3]: https://arxiv.org/html/2603.24621v1 "ARC-AGI-3: A New Challenge for Frontier Agentic Intelligence"
[4]: https://arcprize.org/competitions/arc-agi-3-preview-agents "ARC-AGI-3 Preview Agent Competition"
