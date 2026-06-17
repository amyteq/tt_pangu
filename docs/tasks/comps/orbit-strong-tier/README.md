# Orbit Wars strong-tier突破任务包

本目录是一组可直接给 Claude Code CLI 执行的 task/prompt specs，目标是把 Orbit Wars 从当前 rules-heavy agent 迭代到 **hybrid, model-centric, rule/geometry safety core**，并通过长期 ladder loop 尝试突破 strong-tier cliff（目标 `public μ >= 1200`）。

## 使用方式

建议把本目录解压到 repo 根目录，然后一个 task 一个 worktree/branch 执行。不要一次执行所有任务。

常用执行格式：

```bash
claude --bg \
  --name "OW-P0-research" \
  --permission-mode auto \
  "/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/00-goal-research-kuni05-matchmaking-identity.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable."
```

长期迭代 loop 可以用：

```bash
claude --bg \
  --name "OW-LADDER-loop" \
  --permission-mode auto \
  "/loop Execute loop from docs/tasks/competition-tracking/orbit-strong-tier/prompts/07-loop-ladder-iterate-to-strong-tier.md until strong-tier breakthrough, no runnable tasks remain, or stop conditions trigger. Read the loop file fully first. Treat the loop file as immutable."
```

如果你的 Claude Code 环境没有 `/loop`，用 `/goal` 跑一次 bounded cycle：

```bash
/goal Execute one bounded cycle from docs/tasks/competition-tracking/orbit-strong-tier/prompts/07-loop-ladder-iterate-to-strong-tier.md until its per-cycle acceptance criteria pass or stop conditions trigger.
```

## 推荐执行顺序

1. `00-goal-research-kuni05-matchmaking-identity.md` — 先确认 kuni05-class public source、matchmaking、profile/username mapping。
2. `01-goal-doc-consistency-and-live-loop-baseline.md` — 修正文档状态，确保现有 `ops/` live loop 与最新事实一致。
3. `02-goal-flight-oracle-and-execution-zero-bug.md` — P0，底层执行层零 bug。
4. `03-goal-battlefield-state-ledger-rule-engine.md` — P0/P1，实时战场态势与 ledger。
5. `04-goal-replay-dataset-and-feature-pipeline.md` — P1，可与 2/3 并行做 replay index，但候选标签需等 FlightOracle 稳定后重跑。
6. `05-loop-snorlax-model-training.md` — P1/P2，在 snorlax 上训练 candidate scorer/value model，可与 ladder episode 分析并行。
7. `06-goal-hybrid-policy-integration.md` — P2，model scorer + rule engine + FlightOracle gate。
8. `07-loop-ladder-iterate-to-strong-tier.md` — 长期 online loop：submit → episode analysis → fix/train/enhance → resubmit。

## 并行建议

可以并行：

- Research stream：`00`。
- Foundation stream：`02` + `03`，但两者要共用同一 `core/` schema，避免重复实现 geometry。
- Data stream：`04` 可先做 episode index / raw schema；candidate labels 等 `02` 完成后重算。
- Model stream：`05` 可在 snorlax 等待 dataset v0 时先跑 exploratory EDA / small sample。
- Ladder stream：`07` 可以继续分析线上 episodes，但只有通过 `promotion_gate.yaml` 的版本才能 submit。

不要并行修改同一文件的两个任务，尤其是：

```text
competitions/orbit-wars/agent/main.py
competitions/orbit-wars/ops/*
competitions/orbit-wars/tasks.md
competitions/orbit-wars/tracking.md
competitions/orbit-wars/submissions.md
```

## 核心原则

- Model-centric hybrid，但模型不直接输出连续角度。
- `FlightOracle + BattlefieldState + Ledger + ActionSanitizer` 是所有路线的基础。
- 所有 final actions 必须 deterministic safety-gated。
- `kuni05` public source 只能作为 attributed reference / system study；不能把其成果误标为 from-scratch。
- Kaggle submit/push 仅在 `07-loop` 中按授权、预算、双账号 lane 规则执行。
- 凭证只允许读取 `.vscode/.env.harry` 和 `.vscode/.env.may`，不得打印或写入文档。
- Early stop 是强制规则：前 10/20 episodes 不能保持或持续攀升时标记 weak，准备释放 active slot。
