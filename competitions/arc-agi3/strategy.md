# Strategy — ARC-AGI-3

> English canonical. Detailed Chinese version in `notes_zh.md`. Evidence in `research.md`.
> Phase: **research** — nothing built yet; this is the plan, not a result.

## Current direction
Stand up the `arc-agi` SDK harness, play the 25 public envs, **pick a track**, then build a minimal
exploration baseline before any heavy R&D. The benchmark is wide open (AI < 0.5%, humans 100%), so the
first job is a *working loop with a local RHAE metric*, not a clever model.

## The core challenges (what makes AGI-3 hard)
1. **No instructions / no goal / no demo pairs.** The agent must *discover* mechanics by acting.
   This is the single biggest break from AGI-1/2 — all demo-pair techniques (TTT, program synthesis,
   DSL search) are dead. See `cross-competition.md`.
2. **Exploration is quadratically expensive.** RHAE = `(human/agent actions)²`. Random/brute-force
   exploration that doubles human action count scores 0.25. You must explore *information-greedily*.
3. **Generalization gap is brutal.** StochasticGoose: 12.58% on 6 known envs → 0.25% on the hidden
   set. Overfitting to the 25 public envs (only 18.5% of the benchmark) will not generalize.
4. **No internet at eval ⇒ no hosted LLM at inference.** Any LLM reasoning must run *inside* the
   Kaggle notebook (offline weights, <12h, $10K cap) — so a frontier-API agent is a dev-only tool.
5. **Frontier LLMs are near-zero (< 0.5%).** Raw chat-model reasoning does **not** solve these; the
   missing ingredient is grounded *exploration + world-modeling*, not more reasoning tokens.
6. **Long interactive context.** Many turns × 64×64 frames → history blows up; needs selective
   retrieval / compression (Duke pattern).
7. **Two leaderboards** — Official forbids custom harness; Community allows it. They need different
   stacks; building for the wrong one wastes the whole effort (see D001).

## Open discussions

### D001: Official vs Community track — which do we target?
- status: **open** (decide before building)
- context: Official = fixed minimal prompt, no harness, raw model capability, prize/AGI-eligible.
  Community = full harness/tools/orchestration, not AGI-claim-eligible, but where all early traction is.
- options: (a) Community first; (b) Official only; (c) both, shared perception core.
- current leaning: **(a) Community first** — that's where signal, learning, and RL/harness leverage
  are; the Official board is essentially "wait for a better base model." Revisit if we pretrain a model.
- evidence: StochasticGoose / Arcgentica / Duke are all Community; Official frontier models < 0.5%.
- follow-up: confirm exact qualification rules in the technical paper (arXiv 2603.24621) §eval protocol.

### D002: Model-based RL vs LLM-agent-harness as the primary approach?
- status: **open**
- context: two credible paradigms — (1) train a model-based RL agent (learned frame-predictor world
  model + planner; StochasticGoose lineage; exploits 1–2k FPS headless sim), or (2) an LLM-driven
  agentic harness (offline open-weights LLM that reasons over rendered frames + memory + tools).
- current leaning: **hybrid, RL-leaning** — perception/world-model via a small learned net, with an
  optional LLM for high-level goal inference. Pure-LLM is near-zero today; pure-RL has the only
  non-trivial public score.
- follow-up: prototype both on 2–3 public envs, compare RHAE-per-compute.

### D003: How to fight the generalization gap (public→private)?
- status: open
- options: train across *all 25* public envs + heavy procedural augmentation; meta-learning /
  fast-adaptation so the agent adapts *within* an episode rather than memorizing envs; keep the
  policy small + prior-driven so it can't overfit.
- current leaning: **in-episode adaptation** (the agent must learn each new game live) over
  per-env training — that's literally what the benchmark rewards.

## Hypotheses (all untested — research phase)
- **H1**: An *information-greedy* exploration policy (act to maximally reduce world-model uncertainty)
  beats both random and naive-RL on RHAE, because RHAE punishes wasted actions quadratically.
- **H2**: A learned **frame-predictor world model** (predict next 64×64 frame from action) enables
  short-horizon planning that lifts score well above the 0% LLM floor — model-based > model-free here.
- **H3**: **In-episode fast adaptation** (meta-RL / quick fine-tune on the live episode) generalizes
  to held-out envs far better than per-env training (which overfits the 25 public envs).
- **H4**: For Community track, an **orchestrator (explore / model / plan / memory) + selective history**
  harness over an offline open-weights reasoner beats a single-prompt LLM loop.
- **H5**: Most score comes from **early/tutorial levels across many envs** (per-level cap + later-level
  weighting); a robust "learn the tutorial fast" agent banks broad partial credit before deep levels.

## Technique menu (candidates to improve score)
- **Information-greedy / curiosity exploration**: count-based or prediction-error intrinsic reward;
  empowerment; act where the world model is most wrong. (Directly targets RHAE efficiency.)
- **Model-based RL**: learned dynamics (next-frame predictor) + planning (MCTS / MuZero-style /
  shooting). Headless ≈ 1–2k FPS makes self-play feasible.
- **Object-centric perception front-end**: segment the 64×64 grid into objects (Core-Knowledge
  priors) → compact state → smaller, more generalizable policy/world-model. Shared with AGI-2.
- **Meta-RL / in-episode adaptation**: RL² / fast weights / test-time policy update so the agent
  *learns the game live* — the benchmark's core demand.
- **Hierarchical RL**: option/skill discovery (e.g. "move object to region") for the compositional
  later levels.
- **Goal inference**: detect what changes when you win a tutorial level → hypothesize the goal →
  pursue it on later levels (active goal-setting is one of the 4 tested capabilities).
- **Agentic harness (Community)**: orchestrator + subagents + compressed memory + selective history
  (Arcgentica + Duke patterns) over an offline reasoner.
- **Undo (ACTION7) as cheap rollback**: explore aggressively, undo dead ends — but watch RHAE
  (does undo count as an action? ⚠ verify; if it does, it's not free).
- **Procedural curriculum / self-play**: generate variations of the public envs to train robust
  priors without overfitting the 25 specific games.

## Rejected / avoid
- **Porting the AGI-2 stack directly** (TTT/program-synthesis/DSL) — no demo pairs; scores ~0.
- **Hosted-LLM-API agent as the submission** — no internet at eval; dev-tool only.
- **Overfitting the 25 public envs** — 12.58%→0.25% generalization cliff is the canonical failure.
- **Brute-force / random exploration as a strategy** — quadratically penalized by RHAE.

## Background (the bet)
AGI-3 is the rare Kaggle comp where the *field* is at < 1% and humans at 100% — the headroom is
enormous and the winning approach is **not yet known**. That favors genuine RL/agent research over
recipe-iteration. Highest-EV first move is cheap: a working SDK loop + local RHAE metric + a
non-random exploration baseline, which already beats most of the field's near-zero scores and gives us
a measurement substrate for everything after. See `tasks.md`.
