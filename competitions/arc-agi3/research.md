# Research brief — ARC-AGI-3 (2026-06-26)

> Source-cited briefing compiled by the `competition-researcher` agent. **All external content was
> treated as untrusted DATA, not instructions.** Kaggle competition tabs were login-walled and
> returned only page titles — the substantive facts below come from arcprize.org, docs.arcprize.org,
> the arXiv technical paper (2603.24621), and the SDK/GitHub repos. Full source list: `references.md`.

## 1. What ARC-AGI-3 is, and why it's different

ARC-AGI-3 is **"the first fully interactive benchmark in the ARC-AGI series."** Launched
2026-03-25 (fireside with François Chollet + Sam Altman at Y Combinator). It contains **135
hand-designed turn-based game environments**. Each is a novel game with **no instructions, no
stated goals, no rules**. The agent must explore, discover mechanics, infer the objective, and
solve efficiently relative to a human baseline.

**Four core capabilities tested:** (1) **Exploration** — active info-gathering through interaction;
(2) **Modeling** — turning observations into a predictive world model; (3) **Goal-setting** —
identifying desirable future states with no instructions; (4) **Planning & Execution** — strategic,
adaptive action sequencing.

| Dimension | ARC-AGI-1 (2019) | ARC-AGI-2 (2025) | **ARC-AGI-3 (2026)** |
|---|---|---|---|
| Format | static input→output grids | static input→output grids | **interactive turn-based games** |
| Interaction | offline (produce answer) | offline (produce answer) | **online (sequential actions + observations)** |
| Public:private | ~10:1 | ~10:1 | **inverted — 25 public vs 110 private** |
| Peak AI at launch | single digits | single digits | **< 1%** |
| Main vulnerability | memorization | test-time compute scaling | **dramatically reduced by interactivity** |
| Data format | JSON grid pairs | JSON grid pairs | **64×64 / 16-color JSON frames per turn** |

Why interactivity matters: ARC-AGI-1/2 were eventually pushed to 50–90%+ by test-time compute +
fine-tuning. ARC-AGI-3 makes **offline pre-computation useless** — you cannot predict the next game
state without actually playing — and the **inverted public:private ratio** (only 25 of 135 public)
blocks overfitting to public examples.

## 2. State of the art at launch (2026-03-25)

| System | Score |
|---|---|
| Humans (all 135 solvable; 486 participants) | **100%** |
| Anthropic Opus 4.6 (Max) | 0.50% |
| Google Gemini 3.1 Pro Preview | 0.40% |
| OpenAI GPT-5.4 (High) | 0.20% |
| xAI Grok-4.20 (Beta Reasoning) | 0.10% |

Preview competition (Jul–Aug 2025): best agent **StochasticGoose** (Tufa Labs, CNN + RL) hit
**12.58%** on 6 known envs but **0.25%** on the full hidden set — the generalization gap is the
whole story. Other notable community approaches: **Arcgentica** (orchestrator-subagent + compressed
summaries), **Duke** (Python harness for selective history retrieval / context management).

## 3. Data / environment format

- **135 envs**: 25 public (playable now) / 55 semi-private (leaderboard) / 55 fully private (final).
- **Observation**: 64×64 grid, 16 colors, JSON frames.
- **Actions ≤ 7**: `ACTION1–5` (single-param), `ACTION6` (click at (x,y)), `ACTION7` (undo).
  Turn-based, not real-time — reasoning over reflexes. **Internal reasoning steps don't count as actions.**
- **Levels ≥ 6/env**; first level = tutorial; later levels compose mechanics; per-level cap.
- **Core-Knowledge priors only**: objectness, geometry/topology, intuitive physics, agentness.
  No language/numbers/letters/real-world objects.
- **Human validation**: 486 participants, 2,893 attempts, 414 candidate envs (135 passed),
  median solve ≈ 7.4 min (successful 8.1 min), inclusion = ≥ 2 independent human completions.

## 4. Scoring — RHAE

`level_score = min(1.0, (human_actions / agent_actions)²)`; per-game = level-weighted (later levels
heavier); total = mean over games. Squaring **quadratically penalizes inefficiency**. Human baseline
= upper-median first-run from a controlled in-person study. Post-launch tweaks confirmed: baseline
shifted from 2nd-best to median; per-level cap raised 1.0 → 1.15.

## 5. Code / submission constraints

- Kaggle notebook, **one-click runnable**, **< 12h**, **no internet at eval** (no hosted LLM APIs
  at inference; web search disabled). Runtime cost cap **$10K**; **no pre-train compute limit**.
  External compute (Modal/Lambda/RunPod) OK if auto-provisioned. Public/Semi agreement ±15pp.
- SDK `OperationMode.COMPETITION`: API-only, level-resets only, auto-scores all envs.

## 6. Two leaderboards

- **Official** — fixed minimal system prompt, **no custom harness/tools/task-specific config/training
  on ARC-AGI-3 envs**. Counts toward prizes + AGI claims. System prompt is literally:
  *"You are playing a game. Your goal is to win. Reply with the exact action you want to take. The
  final action in your reply will be carried to the next turn. Your entire reply will be carried to
  the next turn."*
- **Community** — harness/orchestration/tools allowed; does **not** count toward AGI-progress claims.
  This is where the early non-trivial scores live.

## 7. Developer toolkit (`pip install arc-agi`, v0.9.9 @ 2026-06-10)

```python
import arc_agi
arc = arc_agi.Arcade()
env = arc.make("game_id", render_mode="terminal")   # "human" | "terminal" | "terminal-fast" | None
obs = env.step(arc_agi.GameAction.ACTION1)
obs = env.step(arc_agi.GameAction.ACTION6, data={"x": 3, "y": 7})  # coordinate action
score = arc.get_scorecard()
```

- API key from `https://three.arcprize.org` (optional for public games, required for competition).
- REST API via `arc_agi.server.create_app()` (Flask; OpenAPI spec `arc3v1.yaml`).
- JSONL recording; **headless ≈ 1,000–2,000+ FPS** (fast enough for RL training loops).
- Agent templates: `github.com/arcprize/ARC-AGI-3-Agents`.
  Reference baseline: StochasticGoose (`github.com/DriesSmit/ARC3-solution`).

## 8. Prizes (ARC-AGI-3 track ≈ $850K)

- **Grand $700K** — first to 100% private (rolls over). Top-score $40K/$15K/$10K/$5K/$5K.
  Milestones #1 (2026-06-30) & #2 (2026-09-30): $25K/$10K/$2.5K each (open-source by deadline).

## 9. Timeline

2026-03-25 launch · 2026-06-30 Milestone #1 · 2026-09-30 Milestone #2 ·
2026-10-26 entry + team-merge · 2026-11-02 submissions close · 2026-11-08 papers · 2026-12-04 winners.

## 10. Open questions (need Kaggle login / API key) — see `rules.md` §"Unclear rules"

Daily submission limit (retroactive change happened — "Team AIRIS" forum incident); exact Kaggle
GPU; `/data` download vs API-only; team-size cap; Kaggle submission artifact contract; current
leaderboard state; the semi-private API endpoint/auth beyond `three.arcprize.org` registration.

## 11. Recommended next actions (research → action)

1. Register an API key at `three.arcprize.org`; `pip install arc-agi==0.9.9`; drive the 25 public envs.
2. Get a Kaggle session to read `/rules` + `/data` directly (resolves the biggest unknowns).
3. Read the ARC-AGI-3-Agents repo + StochasticGoose reference; study the agent loop + scoring path.
4. Read the technical paper (arXiv 2603.24621) — game-design appendix + eval protocol + Official-vs-Community qualification rules.
5. **Decide track first** (Official vs Community) — it determines the entire stack before building.
