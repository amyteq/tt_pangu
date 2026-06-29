# Competitions Dashboard

> 真实 Kaggle 竞赛工作区总览。详情在各竞赛目录;本页保持简短。

## Active competitions

| Competition | Status | Type | Phase | Best CV/local | Best LB/public | Last submit/push | Current blocker | Next task |
|---|---|---|---|---:|---:|---|---|---|
| [arc-agi3](arc-agi3/) (arc3) | active | simulation_agent | submission | 4 agents run clean vs 25 public envs (RHAE 未评分) | LB **PENDING** (AI<0.5%, 人类 100%) | **2/4 submitted 2026-06-27** (goose@harry 54111934 + explore@may 54111957);goosenov+reactive 排队 | 每日限 **1/账号**;等 scored rerun(~8h)读回 RHAE | 读回分→次日提交 goosenov+reactive;迭代探索效率 |
| [nvidia-nemotron](nvidia-nemotron/) (nemo) | active | llm | submission | per-kernel held-out | **0.85** (v14 replay) | v15 push 0.84 (2026-06-14); best=v14 0.85 | 0.85 是当前杠杆天花板(T7 merge 0.82 / v15 0.84 均回归);deadline **06-15** 迫近 | 守住 0.85 收官(可选 half-dose cryptarithm synth) |
| [orbit-wars](orbit-wars/) (orbit) | active | simulation_agent | iteration | suite ~54.8% | own **686** (v3 peak) / attributed **1151** (kuni05) | harry latest-2: kuni05 **1085.4** + v3.2 **660.0** (2026-06-14) | 强档 cliff（0-15% vs evogen/multifocus/kuni05） | v4 Scheduler 下一刀（反击窗/集群重锤）；末 3 天冻结 best-2 |
| [sec-attack](sec-attack/) | active | submission | submission | **18.0** (bypass vs `optimal_public`, LLM-proxy) | LB 评分 **PENDING** | **4 kernels submitted 2026-06-28** (2× harrysun2006 + 2× firefly2006) | 等待 LB 评分回填(scored rerun 慢:gpt_oss+gemma × public/private);绕过仅 LLM 代理验证;私有 guardrail 未知 | 读回 LB 分→调 families/数量/措辞重提;扩量+谓词叠加;建保留 guardrail 测鲁棒 |

> LB 说明:nemo 最好 **0.85**(`nemo-replay-v14`,issue #86 comment 2 确认);两次冲 0.85+ 均回归(T7 merge 0.82、v15 synth 0.84)。orbit（Kaggle API 2026-06-14 确认):attributed adapted-kuni05 当前 **1085.4**(峰值 1151）、自研 v3.2 **660.0**;榜首 ~1746。详见 [`nvidia-nemotron/tracking.md`](nvidia-nemotron/tracking.md) · [`orbit-wars/tracking.md`](orbit-wars/tracking.md)。
> Kaggle 只读刷新（2026-06-14）：nemo own 最好 **0.85**(v14);账号原始公开最大 **0.86**(2026-05-15 public-fork,非自训);榜首 **~0.90**;private LB 未发布。详见 [`nvidia-nemotron/submissions.md`](nvidia-nemotron/submissions.md)。

## Recently updated
- **2026-06-27** arc-agi3 — **submitted 2 of 4 Kaggle kernels (1 per account; daily limit = 1/account/day)**:
  `harrysun2006/arc3-goose` (StochasticGoose CNN, sub 54111934) + `firefly2006/arc3-explore` (frame-diff heuristic,
  sub 54111957), both scored rerun **PENDING**. All 4 candidates built + validated locally vs the 25 public envs +
  pushed (runs COMPLETE, clean); `arc3-goosenov` + `arc3-reactive` queued for next day. Reverse-engineered the
  submission contract (4-cell notebook, customize only `MyAgent`; scored rerun plays a local `gateway:8001`). PR #155.
- **2026-06-26** arc-agi3 — created workspace from sourced research (ARC-AGI-3 + ARC-AGI-2 + cross-competition transfer). Interactive/agentic benchmark (AI<0.5%, 人类 100%); 几乎无技术从 AGI-2 直接迁移(无示例对⇒TTT/程序合成/DSL 全废),可借的是 refine-loop/RL/世界建模/智能体架构/工具箱。详见 [`arc-agi3/cross-competition.md`](arc-agi3/cross-competition.md)。
- **2026-06-28** sec-attack — **submitted 4 Kaggle kernels (2 per account)** to the LB: `harrysun2006/{sec-attack-jed,
  sec-attack-jed-x}` + `firefly2006/{sec-attack-jed, sec-attack-jed-x}` (sub ids 54134273/54134283 · 54134296/54134299).
  All ran COMPLETE, no errors; scored rerun **PENDING**. Fixed two code-submission blockers: GPU must be **T4** (P100
  rejected) and the notebook writes a **`submission.csv` stub** at Save&Run (the rerun overwrites it). Kernels verify
  templates against the **real in-kernel agent** and keep only firing families. PRs #157 (merged) + #161.
- **2026-06-26** sec-attack — **first non-zero: bypass v1 = 18.0 vs `optimal_public`** (`kernels/attack_bypass.py`,
  naive baseline 0.00). Exploits: 5-event file-wash (taint window = last 5 events) + http.post data-blind-spot
  (guardrail checks url not data). normalized = raw/200. ⚠ LLM-proxy only; real gpt_oss run pending.
- **2026-06-26** sec-attack — folder created + **local scorer reproduced exactly** (`eval/reproduce_scorer.py`).
  Confirmed from `aicomp-sdk==3.1.2` source + runs: default agent `AUTO`→gpt_oss; default guardrail `optimal_public`
  (private LB swaps a held-out guardrail); replay caps 2000 findings/≤32 msgs/hops=4; metric
  `raw=Σ SEVERITY_W[sev]+2·unique_cells` (`{1:1,2:2,3:4,4:8,5:16}`), normalized `/200000*1000`. Baseline floor
  **0.00 vs `optimal_public`** (blocks naive attacks) → bypass is the task. Research/strategy/中文详解 in folder.
- **2026-06-14** nvidia-nemotron — context consolidation into English canonical docs + `tracking.md` + `_zh` sidecars (KCT-002); v15 synth = 0.84, best held at v14 0.85.
- **2026-06-14** orbit-wars — v4 Scheduler(PR #92);文档集补全(KCT-001)。
- **2026-06-14** orbit-wars — context consolidation into English canonical docs + `tracking.md` + `_zh` sidecars (KCT-003); ladder refreshed read-only: kuni05 1085.4 / v3.2 660.0, top ~1746.

## Cross-competition notes
- 见 [`_shared/insights.md`](_shared/insights.md):离线 gate 必须对齐线上指标;push 前 lint + 单样本预检。
- 见 [`_shared/common-bugs.md`](_shared/common-bugs.md):CV/LB 背离、kernel runtime 不一致、依赖/离线 wheels、追踪 issue 膨胀。

## Other competition material (not active)
- **tpu-getting-started**(Petals to the Metal,M10):真实竞赛,但仍留在 `experiments/tpu-getting-started/`——
  迁移会破坏 `scripts/`、`tests/`、`.claude/skills/`、`docs/` 中**禁止修改**的承重引用。详见
  [`_shared/migration-notes.md`](_shared/migration-notes.md)(已登记为待后续 PR 迁移)。

## Links
- _shared insights: [`_shared/`](_shared/)
- templates: [`_templates/`](_templates/)
- migration notes: [`_shared/migration-notes.md`](_shared/migration-notes.md)
