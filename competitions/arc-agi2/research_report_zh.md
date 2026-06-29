# ARC Prize 2026 - ARC-AGI-2 Kaggle 比赛研究报告

生成日期：2026-06-26  
面向：Kaggle / 本地 RTX 4090 + 3090 / KCA + Claude Code 工作流

---

## 0. 研究限制与结论摘要

本报告基于 Kaggle 官方竞赛页、ARC Prize 官方页、ARC-AGI-2 GitHub 数据仓库、ARC Prize 技术指南、ARC-AGI-2 arXiv 论文，以及公开搜索索引中可见的 Kaggle Code / Models / Discussion 页面摘要。Kaggle 的部分页面依赖登录与前端 JavaScript 渲染，原始页面无法稳定抓取全部内容；因此，**Overview / Rules / Data / 评测 / 数据集事实以官方 ARC Prize、Kaggle 官方页、GitHub 与论文为准**，Code / Models / Discussion 中的 notebook 分数、讨论标题和片段应进入 Kaggle UI 再复核。

核心判断：ARC Prize 2026 ARC-AGI-2 不是“再大一点的 LLM prompt”比赛，而是一个**受限算力、无互联网、精确输出、低数据量、强组合泛化**的程序合成 / 神经符号 / test-time adaptation 比赛。最有希望的方案不是单一模型，而是：

1. **符号程序搜索 / DSL solver** 负责高精度、可验证、可解释的任务；
2. **神经模型 / neural prior / TTT 模型** 负责生成候选、排序、补齐难题；
3. **合成数据与任务生成器** 负责训练模型、覆盖技能空间；
4. **两次 attempt 的多样性策略** 负责在同一任务上覆盖两个合理假设；
5. **强本地验证器与错误分类体系** 负责避免 0 分、格式错、过拟合、泄漏与 runtime 超限。

对你的环境而言，RTX 4090 + 3090 很适合做离线合成数据、模型微调、candidate reranking、本地长时间 ablation；Kaggle submission notebook 则应保持轻量、确定性、可复现，严格满足无互联网与运行时限制。

---

## 1. 比赛基本信息

比赛名称：**ARC Prize 2026 - ARC-AGI-2**  
平台：Kaggle  
目标：构建能在 ARC-AGI-2 静态视觉推理任务上达到高准确率的系统。官方目标是推动系统在 Kaggle 效率约束下达到 **85% private evaluation accuracy**。  
提交方式：Kaggle Notebook 生成 `submission.json`。  
约束：Kaggle 评测期间无互联网；奖励资格要求代码与方法开源；外部数据和预训练模型必须满足规则中的公开可获得与许可证要求。

奖金结构（ARC-AGI-2 track）：总计 **$700,000**，包括 Progress Prize、Grand Prize、Bonus Prize。官方 ARC Prize 2026 总奖金池为 **$2M**，包含多个 tracks。

关键时间（官方 ARC Prize 2026 页面）：

- 2026-03-25：比赛启动
- 2026-11-02：Kaggle submissions 截止
- 2026-11-08：papers 截止
- 2026-12-04：结果公布

---

## 2. 任务格式、数据文件与 scoring

### 2.1 ARC-AGI-2 任务格式

每个任务由若干 `train` 输入输出示例和若干 `test` 输入组成。参赛系统需要根据训练示例推断隐藏变换规则，并为每个 test input 输出目标 grid。

Grid 是二维矩阵：

- 元素为整数颜色 ID：0–9；
- 尺寸范围通常为 1x1 到 30x30；
- 训练示例通常约 2–10 对，典型约 3 对；
- 测试输入通常 1–3 个，典型 1 个；
- 比赛中 test output 隐藏。

### 2.2 公开数据文件

Kaggle Data 页面与 ARC-AGI-2 GitHub 仓库显示，公开文件包括：

- `arc-agi_training_challenges.json`
- `arc-agi_evaluation_challenges.json`
- `arc-agi_evaluation_solutions.json`
- `arc-agi_test_challenges.json`
- `sample_submission.json`

GitHub 官方数据仓库说明 ARC-AGI-2 公开数据包含 **1000 个 public training tasks** 与 **120 个 public evaluation tasks**。另有 semi-private 与 private test sets，其中 Kaggle leaderboard / live evaluation 会用到隐藏集，最终评测使用 private tasks。

### 2.3 提交格式与 scoring

对每个 test input，submission 需要给出 **exactly 2 outputs**，通常命名为 `attempt_1` 与 `attempt_2`。如果其中任意一个与 ground truth 完全一致，该 test output 得 1 分，否则 0 分。最终 score 是所有 task test outputs 的平均值。

这意味着：

- pixel partial credit 对正式分数无效；
- 形状、颜色、尺寸、每个 cell 都必须完全一致；
- 两次 attempt 应当在“合理候选”之间做策略性分工，而不是重复同一个输出；
- submission 格式错误、缺失 task、grid 非矩形、颜色越界、attempt 数不对，都可能直接导致 0 分或严重掉分。

建议本地加入严格 checker：

```python
import json

def validate_grid(g):
    assert isinstance(g, list) and len(g) >= 1
    w = len(g[0])
    assert 1 <= w <= 30
    assert 1 <= len(g) <= 30
    for row in g:
        assert isinstance(row, list) and len(row) == w
        for x in row:
            assert isinstance(x, int) and 0 <= x <= 9


def validate_submission(path, expected_task_ids):
    sub = json.load(open(path))
    assert set(sub.keys()) == set(expected_task_ids)
    for tid, outputs in sub.items():
        assert isinstance(outputs, list) and len(outputs) >= 1
        for item in outputs:
            assert set(item.keys()) == {"attempt_1", "attempt_2"}
            validate_grid(item["attempt_1"])
            validate_grid(item["attempt_2"])
```

---

## 3. ARC-AGI-2 为什么难

ARC-AGI-2 相比 ARC-AGI-1 的目标是减少靠 brute force、模板记忆、浅层 pattern matching 获胜的空间。官方资料和论文强调三类挑战：

1. **Symbolic interpretation**：系统要理解颜色、形状、边界、箭头、标记、对象、holes、连接关系等符号语义，而不是仅做图像相似度。
2. **Compositional reasoning**：一个任务往往需要多个规则组合，例如先识别对象，再按大小排序，再复制/移动/裁剪/重色。
3. **Contextual rule application**：同一个颜色或形状在不同任务里可能有不同含义，规则必须从当前示例中归纳出来。

ARC-AGI-2 论文还说明，最终任务经过大规模 human testing：407 名参与者、515 sessions、13,405 attempts；最终 test pair 的平均人类 solved rate 约 75%，平均 test-taker solved rate 约 66%，且每个最终任务至少被 2 名独立人类在 2 次 attempt 内解决。这说明：任务对普通人可解，但对当前 AI 系统非常难，难点不在知识量，而在**低样本抽象、规则归纳、组合泛化、误导性 pattern 的处理**。

---

## 4. Kaggle Code / Models / Discussion 页面公开线索

由于 Kaggle Code / Models / Discussion 页面无法稳定以完整 DOM 抓取，这一节以公开搜索索引摘要为线索，需要在 Kaggle UI 中二次核对。

### 4.1 Code / Notebook 线索

公开索引中能看到：

- `[Baseline] NVARC ARC'25 Winning Solution (for T4x2)`：ARC Prize 2026 相关 notebook，public score 约 10.42，runtime 约 1h13m，GPU T4 x2。
- `ARC_2026D`：公开索引显示 public score 2.50，best 30.14，runtime 约 4h18m，GPU L4 x4。

这表明目前公开 notebook 中已经有较强 baseline / fork / ensemble 线索，但应特别警惕：

- public LB 可能因为样本少而噪声大；
- Kaggle notebook 分数可能来自不同版本与不同硬件；
- 高 public 分不一定能转化到 private；
- Notebook 是否 prize eligible 取决于开源、外部数据、模型许可、无互联网和 reproducibility。

### 4.2 Models 页面线索

公开索引显示 Kaggle Models 页面已有比赛相关模型条目，且显示 “Best public score: 29.31” 一类信息。建议在 Kaggle UI 里重点查看：

- 模型是否公开可下载；
- 是否可在 no-internet notebook 中加载；
- license 是否允许比赛使用与开源提交；
- 模型是否依赖外部 API；
- 权重大小是否能在 Kaggle runtime 内加载；
- 是否来自 ARC-AGI-2 eval/test 泄漏或不合规数据。

### 4.3 Discussion 线索

公开索引中值得关注的讨论方向：

- ARC-AGI-1 部分 eval/test 任务被纳入 ARC-AGI-2 train；因此用 ARC-AGI-1 public tasks 做训练/验证要小心数据重叠与泄漏。
- 有讨论称去年 winning solution 在 AGI2 eval 可达约 31%，而在 AGI1 eval >95%，说明 ARC-AGI-2 难度显著提升。
- 有 hybrid LLM solver、modular engine、historical leaderboard with runtime、0.00 score debugging 等讨论。
- 很多参赛者遇到 submission 格式问题，尤其是 task ID、attempt key、输出尺寸、JSON 结构、test output 数量不匹配。

---

## 5. 2025 / 早期 SOTA 经验

ARC Prize 2025 官方结果和技术综述给了 2026 很强的参考：

- 2025 Kaggle top private score 约 24%，说明在 Kaggle no-internet / runtime 限制下，公开 notebook 系统仍远低于 85%。
- 2025 的强方向包括 NVARC、ARChitects、MindsAI、TRM、CompressARC、SOAR，以及基于大模型的 refinement / verification 系统。
- NVARC 方向公开描述为 synthetic-data-driven ensemble，包含多阶段合成数据生成、改进的 ARChitects-style test-time training 模型和 TRM 组件。
- ARChitects 方向使用 2D masked-diffusion LLM、recursive self-refinement 与 perspective-based scoring。
- MindsAI 方向强调 test-time training pipeline、augmentation ensembles、tokenizer dropout、pretraining 技巧。
- TRM / CompressARC 说明“小模型 + 合适结构 + 任务特化推理”仍有潜力，不一定要靠最大 LLM。

对 2026 的启发：

1. 单纯 prompt LLM 很可能不够；
2. 纯 DSL brute force 容易被 ARC-AGI-2 的任务设计压制；
3. 纯 neural 模型容易生成近似正确但 exact-match 失败的输出；
4. 有 verifier、candidate ranking、test-time adaptation、合成数据和符号组件的 hybrid system 更现实。

---

## 6. 我建议的总体方案：Hybrid Portfolio ARC Solver

### 6.1 总架构

建议把系统做成 portfolio，而不是押注单一 solver：

```text
Task JSON
  ├─ preprocessing / object extraction
  ├─ symbolic DSL solvers
  │    ├─ crop / transform / recolor / copy / tile / count / line / symmetry / gravity / graph solvers
  │    └─ candidate outputs + proof / score
  ├─ neural candidate generators
  │    ├─ TTT model / 2D transformer / diffusion-like masked model
  │    └─ augmentation ensemble outputs
  ├─ LLM-assisted offline rule mining / synthetic data generation
  ├─ verifier / ranker / leave-one-out scorer
  └─ attempt selector
       ├─ attempt_1: most reliable candidate
       └─ attempt_2: diverse alternative candidate
```

### 6.2 Object-centric 表示

ARC 任务很多不是 raw pixel 问题，而是对象与关系问题。建议基础库先完成：

- connected components；
- 颜色分层；
- bounding boxes；
- holes / enclosed regions；
- symmetry axes；
- grids / separators / frames；
- line segments / rays / arrows；
- repeated motifs；
- shape canonicalization；
- D4 transforms（rotate / flip）；
- scaling / tiling；
- object graph（containment、touching、alignment、distance、direction）。

### 6.3 DSL primitives

建议 DSL 覆盖以下 families：

- crop：按 non-background bbox、marker、frame、grid cell 裁剪；
- recolor：颜色映射、major/minor color、legend/key 映射；
- geometry：translate、rotate、reflect、scale、normalize、align；
- object selection：largest/smallest、unique、inside/outside、same shape、same color、hole count；
- construction：copy object、extend line、fill rectangle、connect dots、complete symmetry、draw border；
- tiling：repeat motif、periodic pattern、grid expansion；
- counting：按数量输出尺寸/颜色/重复次数；
- set operations：union/intersection/subtraction/xor of objects or masks；
- compositional pipelines：`select -> transform -> place -> recolor -> compose`。

### 6.4 Candidate search 与 verifier

核心不是生成一个答案，而是生成多个候选并正确排序。建议：

- 对每个 program 在 train pairs 上做 exact-match；
- 使用 MDL / simplicity score 约束过复杂程序；
- leave-one-out 验证：每次拿一个 train pair 当 pseudo-test；
- hard negative detection：如果多个 program 都完美拟合 train，但 test 输出差异大，要把 attempt_2 给最不同的合理解释；
- 输出候选聚类：避免 attempt_1 / attempt_2 只差一两个像素，浪费第二次机会。

### 6.5 Neural prior / TTT 方向

可以在本地 4090/3090 做离线训练或微调：

- 2D grid transformer / masked diffusion style decoder；
- Qwen3 / small multimodal-like grid token model 的 ARC 格式微调；
- TRM-like recurrent reasoning model；
- synthetic ARC generator 训练；
- test-time augmentation：color permutation、D4 transform、example order shuffle、background choice；
- perspective-based scoring：从不同 canonical views 预测，再投票或 rerank。

注意：Kaggle no-internet 下不能调用外部 LLM API；本地大模型更适合离线生成合成数据、写 DSL、产生 candidate families，而不是在 Kaggle evaluation 中联网调用。

---

## 7. 合成数据策略

合成数据可能是 2026 最关键的杠杆之一，但必须避免“看起来像 ARC，实际上只学到表面纹理”。建议：

1. **Program-first 生成**：先定义可执行 transform program，再生成输入输出 pair，确保标签正确。
2. **Skill curriculum**：从单规则任务到两规则、三规则组合任务。
3. **Human-like distractors**：加入误导颜色、无关对象、多个候选 marker、噪声对象。
4. **ARC-AGI-2 风格约束**：限制 grid size、颜色数、示例数量，模拟真实题目。
5. **Hard split**：按 program family 和 skill composition split，而不是随机 split，避免模型只记住模板。
6. **生成器也要验证**：每个 synthetic task 应能被自己的 solver 回放，同时不能太 trivial。

可以建立 `synthetic_catalog.jsonl`，字段包括：

```json
{
  "task_id": "syn_crop_recolor_000001",
  "family": "crop_recolor",
  "skills": ["object_selection", "bbox_crop", "color_mapping"],
  "program": "select(unique_shape).crop().recolor(legend)",
  "difficulty": 3,
  "train_n": 3,
  "test_n": 1
}
```

---

## 8. 提分技巧与工程注意事项

### 8.1 两次 attempt 的策略

- 如果 symbolic solver 高置信 exact-match，attempt_1 用它；attempt_2 给同族但不同假设，或 neural fallback。
- 如果多个候选 train 都完美拟合，attempt_1 选 simplicity / LOO 最强，attempt_2 选输出差异最大的第二强候选。
- 如果没有强候选，attempt_1 用 neural best，attempt_2 用 simple baseline（如 crop / identity / majority / bounding box）中置信最高者。
- 不建议无脑 duplicate attempt，除非 candidate pool 只有一个且其他输出明显无效。

### 8.2 Local validation

建立本地 `arc_eval.py`：

- exact-match scorer；
- pixel accuracy diagnostic；
- task-level solved / pair-level solved；
- per-family error taxonomy；
- runtime profiler；
- JSON submission validator；
- public eval split 的 “do-not-overfit” 报警。

### 8.3 Runtime 管理

- 先运行 cheap solvers；
- 已有完美候选时停止昂贵 search；
- 给每 task 设置预算；
- 对大 grid / 多对象任务动态减小搜索；
- 缓存 object extraction；
- 避免 Python 深递归和无界组合爆炸；
- Kaggle notebook 内所有路径、模型加载、随机种子固定。

### 8.4 防止 0 分

提交前必须检查：

- task IDs 完整；
- 每个 test input 都有 exactly 2 attempts；
- grid 矩形；
- grid 颜色是 int 0–9；
- 尺寸 1–30；
- JSON 可读；
- 不输出 numpy int64 / ndarray；
- 不依赖互联网；
- notebook 能从 clean runtime 一键运行；
- 模型权重、外部数据路径正确挂载。

---

## 9. 适合你的 KCA / Claude Code 实施路线

你已有 KCA、Claude Code CLI、本地 RTX 4090/3090、vLLM/Qwen/gpt-oss 经验。建议按以下节奏推进。

### Phase 0：复现与基线

- 下载官方数据；
- 跑 sample submission；
- 跑公开 baseline notebook（如 NVARC baseline）并记录 public / local score；
- 建立本地 scorer、validator、runtime profiler；
- 建立 `tracking.md` 和 `experiments/*.yaml`。

### Phase 1：符号基础库

- `arc/io.py`：读写与 submission；
- `arc/grid.py`：grid helpers；
- `arc/objects.py`：components / bbox / holes / graph；
- `arc/transforms.py`：D4 / crop / recolor / compose；
- `arc/solvers/*.py`：每个 solver family 独立；
- `arc/rank.py`：candidate ranking；
- `arc/eval.py`：local scoring。

### Phase 2：Portfolio solver

- 先实现 20–40 个高频 solver families；
- 每个 solver 输出 candidates + confidence + explanation；
- 加入 attempt selector；
- 对 public training / local holdout 做 failure taxonomy。

### Phase 3：Synthetic + Neural

- 建 program-first synthetic generator；
- 用 4090 训练小模型或微调 grid-token model；
- 训练 neural reranker，而不是只训练 generator；
- 用 neural model 产候选，再用 symbolic verifier / ranker 过滤。

### Phase 4：Kaggle notebook hardening

- 单 notebook / package 结构清晰；
- 无互联网；
- 模型文件作为 Kaggle Dataset / Model artifact 挂载；
- runtime 低于官方限制并有 margin；
- 输出 deterministic；
- 所有 experiment 有 metadata。

---

## 10. 推荐 Claude Code `/goal` 任务拆分

可以先让 Claude Code 进入 plan mode：

```md
/goal Read the ARC Prize 2026 ARC-AGI-2 competition docs and this research report. Create an implementation epic ARC26-100 with child stories for a hybrid ARC solver. Do not submit to Kaggle, do not call external APIs, and do not use secrets. Focus on repo structure, local scorer, submission validator, object-centric grid library, symbolic solver portfolio, candidate ranker, synthetic data generator, and Kaggle notebook hardening. Produce docs/arc26_epic.md, docs/arc26_stories.md, and docs/arc26_experiment_protocol.md.
```

然后按 story 实施：

```md
/goal Execute ARC26-101: implement local ARC-AGI-2 data loader, exact-match scorer, sample_submission writer, and strict submission validator. Add unit tests using small synthetic tasks. Do not change solver logic yet.
```

```md
/goal Execute ARC26-102: implement object-centric grid analysis utilities: connected components, bounding boxes, holes, color layers, symmetry detection, D4 transforms, shape canonicalization, and object graph relations. Add tests.
```

```md
/goal Execute ARC26-103: implement the first symbolic solver portfolio: identity, crop non-background, bbox crop, recolor mapping, rotate/reflect, translate object, complete symmetry, tile repeat, line extension, and object selection by size/color/uniqueness. Each solver must emit candidates with metadata and confidence.
```

```md
/goal Execute ARC26-104: implement candidate ranking and two-attempt selection using train exact-match, leave-one-out validation, simplicity penalty, candidate diversity, and deterministic tie-breaking. Add evaluation report generation.
```

---

## 11. 风险清单

| 风险 | 影响 | 缓解 |
|---|---:|---|
| Public LB 过拟合 | private 掉分 | local holdout、family split、少看 public feedback |
| 格式错误 | 0 分 | strict validator + clean notebook smoke test |
| runtime 超限 | submission fail | task budget、early stop、profiler |
| 合成数据表面化 | 模型泛化差 | program-first、hard split、skill taxonomy |
| DSL 爆炸 | 搜索慢且过拟合 | MDL penalty、solver family gating |
| neural 输出近似正确 | exact-match 失败 | symbolic verifier / reranker |
| 外部模型许可不合规 | 奖励资格风险 | 只用公开、可下载、许可证明确模型 |
| 数据泄漏 | 取消资格风险 | 区分 train/eval/test，记录数据来源 |

---

## 12. 主要来源

- Kaggle competition: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2
- ARC Prize 2026 overview: https://www.arcprize.org/arc-prize/2026
- ARC-AGI-2 official page: https://www.arcprize.org/arc-agi/2
- ARC-AGI-2 GitHub repository: https://github.com/arcprize/ARC-AGI-2
- ARC Prize technical guide: https://www.arcprize.org/guide
- ARC-AGI-2 paper: https://arxiv.org/html/2505.11831v1
- ARC Prize 2025 results: https://www.arcprize.org/blog/arc-prize-2025-results

---

## 13. 最终建议

如果目标是稳定提高 Kaggle 分数，我建议不要一开始就微调大模型，而是先完成三个最有复利的基础设施：

1. **local scorer + validator + error taxonomy**：防止低级错误，让每次实验可比较；
2. **object-centric symbolic portfolio**：先拿到可解释、可验证的基础分；
3. **candidate ranker + two-attempt diversity**：把已有候选转化为更高 exact-match。

随后再引入 synthetic data、TTT 模型、NVARC/ARChitects/TRM-like 组件。长期最强路线应是 hybrid：符号 solver 保证精确性，neural prior 提供搜索方向，synthetic generator 扩展技能覆盖，verifier 负责从候选中选出最可能 exact-match 的两个答案。
