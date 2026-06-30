# ARC Prize 2026 - ARC-AGI-3

> Canonical language: **English**. Detailed Chinese introduction + ideas in `notes_zh.md`.
> Aliases: `arc3`, `arc-agi-3`. Kaggle slug: `arc-prize-2026-arc-agi-3`.
> ARC-AGI-3 is the **first interactive / agentic** benchmark in the ARC-AGI series — turn-based
> game environments, **not** static input→output grid puzzles. This changes almost everything
> about technique vs ARC-AGI-1/2.

## Status snapshot
- status: **active** (first submissions in flight)
- phase: **baseline / submission**
- current objective: get a non-zero RHAE; 4 candidate agents built, validated locally, pushed to Kaggle
- best known local/CV: agents run clean vs the 25 public envs
- best known LB/public: **explore 0.18 / goose 0.07** (both >> the <0.005 frontier-LLM baseline; humans 1.0)
- current blocker: **daily limit = 1 submission/account/day** → only 2 of 4 submitted today; rest next day
- next task: submit arc3-goosenov + arc3-reactive next day; port explore's action-efficiency into the CNN's exploration

## Submissions — scored (2026-06-27)
| Kernel | Account | Agent | Status | LB |
|---|---|---|---|---|
| arc3-explore | firefly2006 | frame-diff heuristic | COMPLETE (id 54111957) | **0.18** ← beat the CNN |
| arc3-goose (`…-stochasticgoose-cnn`) | harrysun2006 | canonical StochasticGoose CNN | COMPLETE (id 54111934) | **0.07** |
| arc3-goosenov | harrysun2006 | CNN + novelty escape | ready, queued (1/day cap) | — |
| arc3-reactive | firefly2006 | object-centric heuristic | ready, queued (1/day cap) | — |
See `submissions.md` for the log, `kca-arc-agi3.yaml` for the push config, `kernels/agents/` for the agents.

## What is ARC-AGI-3 (one paragraph)
135 hand-built, instruction-free, turn-based games on a 64×64 / 16-color grid. The agent gets
**no rules, no goal, no demo pairs** — it must *explore* to discover mechanics, *model* the world,
*infer the goal*, then *plan/execute* efficiently. Scoring is **RHAE** = `(human_actions/agent_actions)²`
per level (capped 1.0), so over-exploration is punished quadratically. Action space ≤ 7
(`ACTION1–5` simple, `ACTION6` = click at (x,y), `ACTION7` = undo). Splits: 25 public / 55 semi-private
(leaderboard) / 55 fully private (final scoring). See `research.md` for full detail + sources.

## Key links
- **how it works (agent logic + submission flow, mermaid)**: ./how-it-works.md
- rules (evidence-based, ⚠ flags unknowns): ./rules.md
- ARC-AGI-3 research brief: ./research.md
- owner research report (中文, full): ./research_report_zh.md · Q&A: ./explore.md
- ARC-AGI-2 + prior-winner research brief: ./arc-agi2-research.md
- **cross-competition (AGI-2 ↔ AGI-3) transfer**: ./cross-competition.md
- strategy / ideas / hypotheses / challenges: ./strategy.md
- detailed Chinese intro (用户介绍): ./notes_zh.md
- tasks: ./tasks.md
- insights: ./insights.md
- references / sources: ./references.md
- submissions: ./submissions.md
- bugs: ./bugs.md
- machine-readable metadata: ./competition.yaml

## Two leaderboards (decide early — it constrains the whole stack)
- **Official** — fixed minimal system prompt, **no custom harness**, no hand-built tools, no
  task-specific config. Measures *raw model capability*. Prize-eligible / counts toward AGI claims.
- **Community** — custom harness, orchestration, tools all allowed. Measures *system capability*.
  Does **not** count toward AGI-progress claims. Most early traction (StochasticGoose 12.58%,
  Arcgentica, Duke) is here.

## Current top 3 priorities
1. **Tooling**: `pip install arc-agi`, get an API key, drive the 25 public envs in `human`/`terminal`
   render; record episodes. Mirror the nemo `kca-<slug>.yaml` + flat `kernels/`+`lib/` pattern.
2. **Track decision**: Official (raw model) vs Community (harness) — they require different stacks.
   Recommendation leaning **Community** first (where signal/learning is, and where RL/harness work pays off).
3. **Baseline**: a minimal exploration agent (random + frame-diff curiosity) to establish a non-zero
   floor and a working submission notebook (one-click, <12h, no-internet eval).

## Latest update
- date: 2026-06-26
- source: research agents over arcprize.org / arXiv 2603.24621 / docs.arcprize.org / Kaggle (login-walled)
- summary: Created competition workspace from research. ARC-AGI-3 confirmed as interactive agentic
  benchmark; near-zero AI baseline (<0.5%) vs 100% human. Almost **no technique transfers** directly
  from ARC-AGI-2 (no demo pairs ⇒ no TTT, no program synthesis, no DSL search); what *does* transfer
  is the **refinement-loop meta-pattern**, RL/world-modeling, agent-architecture, and context
  management. See `cross-competition.md`.

## ⚠ Immediate verification items (need Kaggle login / API key)
- Exact daily submission limit (a retroactive change happened mid-competition — "Team AIRIS" forum incident).
- Exact Kaggle GPU spec for this competition (T4×2 / P100 / L4×4 all plausible from prior years).
- Whether the `/data` tab is a real file download or purely API access (evidence: API access).
- Team-size cap for the 2026 main competition (preview was 10).
- Milestone #1 (open-source, **2026-06-30**) — 4 days out; we have nothing to submit, so this milestone is not in scope.
