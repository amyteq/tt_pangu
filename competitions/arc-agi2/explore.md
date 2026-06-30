# Q1
详细阅读了解[ARC Prize 2026 - ARC-AGI-2](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2) 这个比赛, 深入Overview, Data, Code, Models, Discussion 等pages 并做全面的研究, 向我做详细介绍, 并给出你的ideas, 你认为存在的挑战, 以及可以提高成绩的技术和技巧! 最后提供分析文件的下载链接!

# A1
已完成研究，并整理成 Markdown 分析文件：
[下载 ARC Prize 2026 ARC-AGI-2 中文研究报告](sandbox:/mnt/data/arc_prize_2026_arc_agi_2_research_report_zh.md)

## 核心结论

ARC Prize 2026 - ARC-AGI-2 是一个**静态视觉抽象推理 benchmark**，目标不是让模型背题或用大模型 API  brute force，而是在 Kaggle Notebook、无互联网、有限运行时间内，对每个 test grid 输出 **exactly 2 个候选答案**；任意一个与 ground truth 完全一致才得分。官方 ARC-AGI-2 track 的 Bonus Prize 要求 private evaluation 达到 **85%**，且奖励资格要求开源、可复现。([ARC Prize][1])

数据结构仍是 ARC 风格：每个任务包含少量 `train` input/output 示例和隐藏 `test` input，需要系统归纳规则并生成输出 grid。官方 GitHub 仓库说明公开集包含 **1000 个 public training tasks** 和 **120 个 public evaluation tasks**，另有 semi-private 与 fully-private 隐藏集；grid 是 0–9 颜色整数矩阵，典型任务只有约 3 个示例。([GitHub][2])

ARC-AGI-2 的难点在于它被设计成“人类能做、AI 很难”：官方论文/页面说明这些任务经过 400+ 人类参与者校准，每个最终任务至少被 2 名非专家人类在 2 次以内解出，但当前 AI 系统仍很低分。([ARC Prize][3])

## 我对比赛方向的判断

最靠谱的路线不是单一 LLM prompt，而是 **Hybrid Portfolio ARC Solver**：

```text
object-centric parsing
  → symbolic DSL / program search
  → neural candidate generator / TTT model
  → verifier + ranker
  → attempt_1 / attempt_2 diversity selector
```

也就是说：

1. **符号程序搜索**解决高置信、可验证任务，例如 crop、recolor、rotate、reflect、tile、line extension、symmetry、object selection。
2. **神经模型 / TTT / masked grid model**负责生成候选、补齐符号 solver 覆盖不到的任务。
3. **合成数据生成器**负责扩展技能空间，但最好是 program-first，而不是只生成“像 ARC 的图案”。
4. **candidate verifier / ranker**非常关键，因为正式分数是 exact match，没有 partial credit。
5. **attempt_1 / attempt_2** 应该覆盖两个不同合理假设，而不是重复输出。

2025 的官方结果也支持这个判断：Kaggle top private 约 24%，NVARC 是 synthetic-data-driven ensemble；ARChitects 使用 2D-aware masked-diffusion LLM、recursive refinement 和 perspective scoring；MindsAI 强调 test-time training、augmentation ensemble、tokenizer dropout 等工程化方法。([ARC Prize][4])

## Code / Models / Discussion 观察

Kaggle 的 Code / Models / Discussion 页面很多内容依赖登录和 JS 渲染，我能读取到的是公开索引摘要，建议你之后在 Kaggle UI 中复核。公开线索显示，已有 NVARC baseline / improved notebooks，例如一个 NVARC baseline public score 约 10.42，另一个 NVARC improved public score 约 18.19；也有 `ARC_2026D` notebook 的 best score 约 30.14。([Kaggle][5])

Discussion 里值得关注的点是：有参赛者提到上一年 winning solution 在 AGI2 eval 达到约 31%，但在 AGI1 eval 超过 95%，这说明 ARC-AGI-2 明显压制了 ARC-AGI-1 上的模板化/过拟合路线。([Kaggle][6])

## 对你环境的建议

你有 RTX 4090 / 3090、本地 vLLM、KCA 和 Claude Code 工作流，适合这样推进：

第一阶段先不要急着微调大模型，先做：

* `arc_eval.py`：exact-match scorer、pixel diagnostic、submission validator；
* `objects.py`：connected components、bbox、holes、shape canonicalization、symmetry、object graph；
* `solvers/`：20–40 个 symbolic solver families；
* `ranker.py`：train exact-match、leave-one-out、simplicity penalty、candidate diversity；
* `submission.py`：严格生成 Kaggle `submission.json`。

第二阶段再做 synthetic data：

* program-first task generator；
* skill taxonomy；
* hard split；
* 4090 上训练 neural prior / reranker；
* Kaggle notebook 内只加载最终轻量模型和 solver portfolio。

第三阶段做 Kaggle hardening：

* no internet；
* deterministic seed；
* runtime profiler；
* clean notebook smoke test；
* submission 格式 checker；
* public LB 反馈记录到 `tracking.md`，避免过拟合。

## 最大挑战

最大的挑战不是“知道 ARC 是什么”，而是：

* 低样本规则归纳；
* 多规则组合；
* contextual meaning；
* exact-match 输出；
* public LB 噪声与 hidden private 泛化；
* runtime 限制；
* 合成数据不当导致模型学到表面 pattern；
* 公开 notebook fork 很容易变成 public leaderboard overfit。

我在报告里已经把比赛规则、数据结构、公开 notebook 线索、2025 SOTA、解法架构、提分技巧、KCA/Claude Code 实施路线和可直接使用的 `/goal` prompts 都整理好了。

[1]: https://arcprize.org/competitions/2026/arc-agi-2 "ARC Prize 2026 - ARC-AGI-2 Competition"
[2]: https://github.com/arcprize/ARC-AGI-2 "GitHub - arcprize/ARC-AGI-2 · GitHub"
[3]: https://arcprize.org/arc-agi/2 "ARC-AGI-2"
[4]: https://arcprize.org/blog/arc-prize-2025-results-analysis "ARC Prize 2025 Results and Analysis | ARC Prize"
[5]: https://www.kaggle.com/code/amanatar/nvarc-improved-arc-agi-2-2026/comments?utm_source=chatgpt.com "NVARC Improved — ARC-AGI-2 2026"
[6]: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/discussion/684857?utm_source=chatgpt.com "ARC Prize 2026 - ARC-AGI-2 | Kaggle"
