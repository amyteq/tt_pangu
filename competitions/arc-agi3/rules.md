# Rules — ARC-AGI-3

> Only **evidence-backed** facts. Unconfirmed items are explicitly marked «⚠ 待确认».
> Primary sources: arcprize.org/competitions/2026/arc-agi-3, arcprize.org/policy,
> docs.arcprize.org, arXiv 2603.24621. Kaggle tabs were login-walled — see `research.md`.

## Problem
Interactive, turn-based **game environments**. The agent receives an observation, takes an action,
receives the next observation, and repeats until the level is won/lost. **No instructions, no stated
goal, no rules, no demonstration pairs.** The agent must explore to discover mechanics, model the
world, infer the objective, and plan an efficient solution. (Contrast: ARC-AGI-1/2 are offline
input→output grid puzzles.)

## Data
- **135 environments** total: **25 public** (playable now via browser/API) / **55 semi-private**
  (leaderboard, API-only) / **55 fully private** (final scoring, partner-only).
- **Observation**: a 64×64 grid, each cell one of **16 colors**, delivered as JSON frames.
- **Action space ≤ 7**: `ACTION1–ACTION5` (single-parameter, game-specific/directional),
  `ACTION6` (coordinate click — needs `{x, y}`), `ACTION7` (undo, where supported).
- **Levels**: ≥ 6 per environment; earliest level is a tutorial; later levels compose mechanics.
  Per-level score cap prevents one bad level from sinking the whole environment.
- **Priors restricted to Core Knowledge** only: objectness, basic geometry/topology, intuitive
  physics, agentness. **No language, numbers, letters, or real-world objects.**
- **Access**: via the `arc-agi` Python SDK / REST API, **not** a conventional file download.
  «⚠ 待确认» whether Kaggle `/data` tab exposes any downloadable file (evidence points to API-only).

## Metric
- **RHAE (Relative Human Action Efficiency)**, pronounced "Ray":
  `level_score = min(1.0, (human_actions / agent_actions)²)`.
- Per-game score = weighted average over levels (later levels weighted more);
  total = average over all games. **Squaring punishes over-exploration quadratically**
  (2× the human action count ⇒ 0.25, not 0.5).
- Human baseline (the denominator) = upper-median first-run performance from a controlled in-person
  study (486 participants, 2,893 attempts; median solve ≈ 7.4 min).
- **Internal agent reasoning steps do NOT count as actions** — only environment-state-changing
  actions count. (Reasoning is "free"; acting is what's scored.)
- «⚠ 待确认» post-launch scoring tweaks beyond the two confirmed ones (baseline shifted to median;
  per-level cap raised 1.0 → 1.15 at one point).

## Submission format
- A **Kaggle notebook**, **one-click runnable** (fully automated, no manual config/clicks).
- Interacts with the competition environment via the `arc-agi` SDK in `OperationMode.COMPETITION`
  (API-only, level-resets only / no full game reset, auto-scores all environments).
- «⚠ 待确认» exact `submission.*` artifact expectations on the Kaggle side (the SDK auto-scores;
  confirm what file Kaggle ingests).

## Constraints
- **Runtime < 12 hours** wall-clock.
- **No internet access during evaluation** ⇒ **cannot call hosted LLM APIs at inference time**
  (no GPT/Claude/Gemini API at eval). Web search explicitly disabled (could leak semi-private data).
- **Runtime cost cap: $10,000 USD** (incl. any commercial API). **No pre-training compute/cost limit.**
- External compute providers (Modal/Lambda/RunPod) acceptable **if provisioned automatically** in-notebook.
- Public/Semi-Private score agreement tolerance: **±15 percentage points** (looser than AGI-2's ±3pp,
  reflecting higher interactive-env variance).
- «⚠ 待确认» exact Kaggle GPU spec (T4×2 / P100 / L4×4 from prior years — needs login).

## Two leaderboards (rule-level distinction)
- **Official**: fixed minimal system prompt ("You are playing a game. Your goal is to win. Reply
  with the exact action…"), **no custom harness / tools / task-specific config / prior task-specific
  training on ARC-AGI-3 envs**. Counts toward prizes + AGI claims.
- **Community**: custom harness, orchestration, tools, optimization all allowed. Does **not** count
  toward AGI-progress claims.

## Deadline / schedule
- 2026-03-25 — competition launched.
- 2026-06-30 — **Milestone #1** (open-source by deadline → $25K/$10K/$2.5K). *Not in scope for us.*
- 2026-09-30 — **Milestone #2** (same structure).
- 2026-10-26 — **Entry deadline + Team merger deadline**.
- 2026-11-02 — **Submissions close**.
- 2026-11-08 — Research papers due (Paper Track).
- 2026-12-04 — Winners announced.

## External data / model / open-source rules
- **Any model architecture** permitted (not limited to LLMs). Unlimited pre-training data/compute.
- Public/commercial APIs may be used **during development** but **not at evaluation** (no internet).
- **Open-source mandate**: prize-eligible solutions must be released **CC0 or MIT-0** before
  receiving private evaluation scores.

## Prizes (ARC-AGI-3 track ≈ $850K of the $2M total)
- **Grand Prize $700K** — first agent to reach **100%** on the private set (rolls over if unclaimed).
- Top-score: $40K / $15K / $10K / $5K / $5K (ranks 1–5).
- Milestones #1 & #2: $25K / $10K / $2.5K each (open-source by the deadline).

## Unclear rules (⚠ 待确认 — need Kaggle login / API key)
1. Exact **daily submission limit** (a retroactive change happened mid-competition — "Team AIRIS" forum incident).
2. Exact **Kaggle GPU** type/quota for this competition.
3. Whether `/data` is a file download or purely API access.
4. **Team-size cap** for the 2026 main competition (preview was 10).
5. Exact Kaggle-side **submission artifact** contract vs the SDK's auto-scoring.
6. Current **leaderboard state** (3 months elapsed since launch; no public post-launch summary found).
