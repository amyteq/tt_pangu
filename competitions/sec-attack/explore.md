# Q1:
详细阅读了解[AI Agent Security - Multi-Step Tool Attacks](https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/overview) 这个比赛, 深入Overview, Data, Code, Models, Discussion 等pages 并做全面的研究, 向我做详细介绍, 并给出你的ideas, 你认为存在的挑战, 以及可以提高成绩的技术和技巧! 最后提供分析文件的下载链接!

# A1:
已经完成研究，并整理成中文 Markdown 报告：

[下载分析报告：ai_agent_security_multi_step_tool_attacks_research_zh.md](sandbox:/mnt/data/ai_agent_security_multi_step_tool_attacks_research_zh.md)

## 核心结论

这个比赛不是普通 prompt jailbreak，也不是传统 Kaggle 表格预测题，而是一个 **algorithmic red-team / agent trajectory search** 比赛：你提交 `attack.py`，官方评测器加载后，让你的攻击算法生成可重放的 multi-step prompt/tool chains；评测器再在 fresh environment 中 replay，并根据隐藏 security predicates 打分。官方页面描述目标是开发 attack algorithms，用来发现 tool-using AI agents 的可复现多步失败；Data 页面也明确这是 JED Red-Team Attack benchmark。([kaggle.com][1])

评分核心是 0–1000 的 normalized attack score，奖励 **successful security-predicate violations + severity + diversity**。因此，高分方向不是堆大量相似 payload，而是构建能覆盖多个安全谓词、多个工具调用图、多个数据流模式的可复现攻击库。([kaggle.com][2])

官方评测机制会 replay attack moves，并对 replay 结果执行 security predicate 判断；公开页面还显示提交逻辑会自动加载 `attack.py` 并生成 `submission.csv`，公开片段中能看到 `gpt_oss_public/private` 和 `gemma_public` 这类 score row。([kaggle.com][1])

## 我认为的 winning direction

最有希望的路线是做一个 **Predicate-Aware Attack Search Engine**：

```text
seed scenarios
  → prompt / trajectory mutation
  → run against target model/environment
  → collect tool trace
  → deterministic replay
  → infer predicate signal
  → minimize chain
  → diversity signature dedup
  → select top candidates
```

四类重点 predicate 应分别建库：

1. **Exfiltration**：诱导 agent 把 secret/token/protected data 发到外部 sink。
2. **Untrusted-to-action**：让不可信内容触发 privileged tool action。
3. **Destructive write**：诱导 agent 删除、覆盖、修改受保护资源。
4. **Confused deputy**：让有权限的 agent 代表攻击者执行本不该执行的动作。

公开 Code 页面已经出现了几个很有参考价值的方向，比如 “Baseline Solution - 4.900”、 “V5 Verify 9.545 Exact”、 “Verify-and-Keep”、 “Trajectory Search”、 “Diversity Optimized Multi-Step Agent Red Teaming” 等。它们共同说明：**verify-and-keep、deterministic replay、predicate diversity、trajectory-level search** 是主流有效路线。([kaggle.com][3])

## 主要挑战

最大挑战有四个：

第一，**hidden sparse reward**。官方谓词隐藏，很多看起来“接近成功”的轨迹可能得分为 0。

第二，**reproducibility**。LLM 工具调用有随机性；不能 replay 的 attack chain 基本没有价值。

第三，**public/private mismatch**。公开讨论中有人提到 public leaderboard 可能不能验证所有 attack types，所以不能只追 public 分数，要保持四类 predicate 和两个模型的覆盖。([kaggle.com][4])

第四，**runtime budget**。公开 Evaluation/Discussion 线索显示目标模型会 sequential evaluation，并有 9,000 秒级别预算；也有页面片段出现过 18,000 秒表述差异，所以工程上应按更保守的 9,000 秒/阶段设计 anytime algorithm。([kaggle.com][5])

## 提分技巧摘要

建议不要从“写更狠的 prompt”入手，而是从 **工具调用图和安全数据流** 入手。每条 candidate 都应记录：

```text
predicate_type
tool_call_graph_shape
trusted_source / untrusted_source
sink_channel
secret_pattern
write_target_type
endpoint_bucket
prompt_style_family
chain_length_bucket
```

然后用类似下面的选择目标：

```text
candidate_value =
    severity_estimate
  + novelty_bonus
  + replay_confidence_bonus
  + cross_model_bonus
  - length_penalty
  - runtime_penalty
```

你的 RTX 4090 / Void Linux 本地环境适合做 candidate generation、mutation、prompt family clustering、failure taxonomy、surrogate classification；但最终是否得分必须以 Kaggle 官方 replay 为准。目标模型包含 GPT-OSS 与 Gemma 4；OpenAI 官方说明 gpt-oss-20b 是 open-weight reasoning model，可在 16GB memory 级别设备运行，Google 也把 Gemma 4 描述为面向 advanced reasoning 和 agentic workflows 的开放模型。([OpenAI][6])

## 最建议你下一步做什么

先复现公开 baseline，确认 `attack.py` 提交链路无误；然后做 V1 “Verify-and-Keep” 框架，再扩展到 predicate-balanced mutation search。不要一开始就大规模 fuzz，否则很容易被 runtime、不可复现轨迹、public/private mismatch 卡住。

报告里我已经附上了一个可直接给 Claude Code 使用的 `/goal` prompt，用来在你的 KCA 项目里建立 `overview.md / strategy.md / tracking.md / attack.py skeleton` 研究脚手架。

[1]: https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/overview?utm_source=chatgpt.com "AI Agent Security - Multi-Step Tool Attacks"
[2]: https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks?utm_source=chatgpt.com "AI Agent Security - Multi-Step Tool Attacks"
[3]: https://www.kaggle.com/code/nawfeelrahman1124444/baseline-solution-4-900?utm_source=chatgpt.com "Baseline Solution - 4.900 🔥🫡"
[4]: https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/discussion/711457?utm_source=chatgpt.com "AI Agent Security - Multi-Step Tool Attacks"
[5]: https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/overview/evaluation?utm_source=chatgpt.com "AI Agent Security - Multi-Step Tool Attacks"
[6]: https://openai.com/index/introducing-gpt-oss/?utm_source=chatgpt.com "Introducing gpt-oss"

