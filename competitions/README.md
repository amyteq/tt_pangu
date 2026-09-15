# Competitions Dashboard

> 真实 Kaggle 竞赛工作区总览。详情在各竞赛目录;本页保持简短。

## Competitions

> Ranks 2 in ADR-0022 §3's precedence order: this table is a **mirror** of each
> `competitions/<slug>/competition.yaml`, never an independent record. `State` is the canonical
> ADR-0022 §3 token (side states carry `resume_state` in the YAML); `Status` is a fact about the
> competition — `open | closed | unknown`, is the official competition submission window open — not about us.
> On any disagreement the YAML is right and this row is stale.

| Competition | State | Type | Status | Best CV/local | Best LB/public | Last submit/push | Current blocker | Next task |
|---|---|---|---|---:|---:|---|---|---|
| [arc-agi3](arc-agi3/) (arc3) | PAUSED_BUDGET | simulation_agent | open | `cv_score: null` —— 本地 RHAE 未计算(4 个 agent 本地跑通 ≠ 已评分) | LB **explore 0.18** / goose 0.07 (AI<0.005, 人类 100%) | **2/4 scored 2026-06-27** (explore@may 0.18 + goose@harry 0.07);goosenov+reactive 自 06-27 起排队未提交 | `verified_daily_limit` 未填 → §6 拒绝对 null cap 做预留(`resume_state: PRE_SUBMIT_GATE`);启发式(0.18)>CNN(0.07) | 先按 §6/A3 填 `verified_daily_limit` + `verified_reset_boundary`(带来源与日期),再提交排队的两个 kernel;然后把 explore 的动作效率移植进 CNN 探索 |
| [nvidia-nemotron](nvidia-nemotron/) (nemo) | FINDINGS | llm | closed | per-kernel held-out(无单一 canonical CV) | **public 0.86 / private 0.85** (`nemo-merge-soup`,已 select) | merge-soup 0.86 破 v14 0.85 天花板(2026-06-15);private 2026-06-16 发布 | 已收官,private 已发布,post-mortem 已写。留给结论的发现:全期最好的 **private**(eq-aug 0.86/0.86)是在 06-15 截止**之后**的 late window 才跑出来的 —— coverage 这个 lever 赛前就在手上 | 写结论:(1) 可比互补 adapter 的 model-soup 超过每个成员;(2) coverage 是 lever、dose 不是(×2 私榜掉到 0.82);(3) eq-aug 不能 soup;(4) public→private 稳,唯一加分的 hedge 是公榜更弱的 b2。再做 T12 本地指标、KCA-core YAML(#85) |
| [orbit-wars](orbit-wars/) (orbit) | FINDINGS | simulation_agent | closed | suite-avg **0.548** (v2.1) | final eligible **unknown** (`best.public_lb: null`); historical own **703.9**(v4 Scheduler,sub 53730511,06-16 已结算、后来被替换) / attributed **1151.0**(adapted-kuni05 峰值;06-16 为 1069.9) | **B11 rotfix ×2 (2026-06-17, subs 53769740 / 53769744)** —— 最后一批自研提交,μ 未记录 | 已于 2026-06-23 收官。两个遗留疑点:(1) 最后提交的 rotfix 对 μ 从未结算记录,所以真实终值未知(703.9 是被它顶掉的那个 agent 的实测值);(2) 最终排名未在收官前抓取 | 写结论:(1) INS-009 —— 强档 cliff 主要是 B11(行星自转差一拍)而非策略:修完 vs evogen 13.8%→45.0%(+31pt)、入日 9%→0%,推翻了「7 个单机制 lever 全失败」的旧叙述;(2) 本地 arena 在自家集群内失去分辨力(μ640-703 一片模糊),天梯探针优于本地门;(3) rotation-relay 已被定量推翻。若 API 仍可查,补回 53769740 / 53769744 的结算 μ |
| [sec-attack](sec-attack/) | FINDINGS | simulation_agent | closed | 18.0 (bypass vs `optimal_public`, LLM-proxy) | final eligible **unknown** (`best.public_lb/private_lb: null`); observed candidate **7.200 / 1.800** (`sec-attack-jed-xl`, sub 54183733, eligibility unverified) | xl v1 scored **7.200** (2026-06-29);前一批 4 subs 最好 2.400 | 已于 2026-09-01 收官。**遗留疑点**:最终 4,186 行榜单里查无我们两个 COMPLETE 提交(7.200 本应 ~3115/4186,榜首 46.425)—— 可能从未 *select* 过提交 | 写结论:breadth 线性放大 3× 未见天花板;private 恒等于 public/4(固定切分,非更严 guardrail);以及「提交前务必显式确认 selection」这一条 |
| [arc-agi2](arc-agi2/) (arc) | WAIT_HUMAN | reasoning (abstraction) | open | **0.0** (`cv_score`) —— oracle harness 100%,TTT/RE-ARC 三次均 0/20 | none yet — LB top **50.56** (nvbanana), 967 队, 账号已报名 | none yet (no Kaggle submit) | 连续**三次** eval 都 **0%**(0.5B / 4B+ARC2-pretrain / 4B+RE-ARC-pretrain 2026-06-30)。RE-ARC pipeline 已**建好并端到端验证**,缺的是**剂量**:比冠军配方低约 **100×**(256× aug / ~98 H100-h / DFS decode / 8B)。卡在**方向决策**,不是卡在代码(`resume_state: HUMAN_DIRECTION`) | 把方向分叉交给 human(本表 / #199):(a) 按完整配方投多日多卡算力(并填 `max_gpu_hours_per_cycle`),或 (b) 转 Grand-Prize writeup、以这条已验证的 pipeline 为交付物。`decision_id: null` = 还没有请求通道(#197),不是没有待决 |

> LB 说明:nemo 最好 **0.86**(`nemo-merge-soup` = v14+c1+b1 的 SVD rank32 模型汤,合规自训;见 [`nvidia-nemotron/tracking.md`](nvidia-nemotron/tracking.md) 2026-06-15 快照 = rank 1 `competition.yaml:best.public_lb`);此前 v14 replay 0.85 为天花板,两次冲 0.85+ 曾回归(T7 merge 0.82、v15 synth 0.84)。orbit(最新一次只读 ladder 刷新 2026-06-16):自研 **v4 Scheduler 703.9**(历史测量，后来被替换；rank 1 的最终有效 `best.public_lb` 为 null)、attributed adapted-kuni05 **1069.9**(峰值 1151);榜首 ~1746。此后 06-17 提交的 B11 rotfix 对(53769740 / 53769744)μ 未结算记录。详见 [`nvidia-nemotron/tracking.md`](nvidia-nemotron/tracking.md) · [`orbit-wars/tracking.md`](orbit-wars/tracking.md)。
> nemo private LB **已于 2026-06-16 发布**(两个账号都收在 **0.85** private;harrysun2006 公榜 150/4350,私榜榜首 0.92,public→private 无 shake-up)。按 ADR-0022 §3 的 `best` 规则,rank 1 记的是**有效**最好成绩 = 已 select 的 soup **0.86 / 0.85**;全期最好的 private 是 `nemo-eq-aug` 的 **0.86 / 0.86**,但它在 06-16 09:22、即 06-15 截止**之后**的 late window(100/team/day)才跑出来,不计名次,所以只写在 rank 3 的 [`nvidia-nemotron/submissions.md`](nvidia-nemotron/submissions.md) 与 [`postmortems/2026-06-16-final-postmortem.md`](nvidia-nemotron/postmortems/2026-06-16-final-postmortem.md) 里。

## Recently updated
- **2026-06-29** sec-attack — **real LB scores in: all 4 subs non-zero, best public 2.40** (`sec-attack-jed-x`,
  fast-breadth direct+deputy max40); balanced=1.44 (×2, deterministic), filewash-heavy=1.08. Lever = scale
  fast-breadth → pushed `harrysun2006/sec-attack-jed-xl` (direct+deputy, max120/fanout60) for the next submit.
- **2026-06-29** arc-agi2 — **full TTT pipeline built + validated, but rung-1/rung-2 score ~0%.** Model-agnostic
  core (augment/serialize/ttt_data/selection/run, 35 tests, oracle decode→100%) + GPU layer (per-task LoRA TTT)
  + offline pretrain, run on snorlax. Qwen2.5-0.5B 0/10→0/20; **Qwen3-4B + pretrain (loss 0.16) still 0/20.**
  Finding: **model size isn't the lever — the data pipeline is** (RE-ARC + synthetic teach rule *execution*;
  training-task pretrain only memorizes, which ARC-2 eval defeats). `how-it-works.md` has the mermaid flows.
  No Kaggle submit. PR #159.
- **2026-06-27** arc-agi3 — **2 of 4 submitted + SCORED**: `firefly2006/arc3-explore` (frame-diff heuristic) =
  **0.18**, `harrysun2006/arc3-goose` (StochasticGoose CNN) = **0.07** — the **no-NN heuristic beat the CNN** (RHAE
  rewards parsimony; the online-trained CNN burns actions learning). Both >> the <0.005 frontier-LLM baseline.
  All 4 candidates built + validated locally vs the 25 public envs + pushed (runs COMPLETE, clean); `arc3-goosenov`
  + `arc3-reactive` queued for next day (daily limit = 1/account/day). Reverse-engineered the submission contract
  (4-cell notebook, customize only `MyAgent`; scored rerun plays a local `gateway:8001`). PR #155.
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
