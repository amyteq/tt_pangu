# Insights — ARC-AGI-3

## Competition-specific insights

### INS-001: AGI-3 breaks all demo-pair techniques
- type: fact
- confidence: high
- evidence: `research.md` §1 (no demo pairs / no instructions); `cross-competition.md` table.
- transfer scope: AGI-3 only (the *reason* AGI-2 techniques don't port).
- status: validated
- notes: TTT, program synthesis, DSL search all need input→output pairs. AGI-3 has none. This is why
  frontier LLMs sit < 0.5%.

### INS-002: RHAE punishes exploration quadratically
- type: rule
- confidence: high
- evidence: `rules.md` metric: `(human/agent actions)²`, cap 1.0/level.
- transfer scope: AGI-3 strategy (drives the whole exploration design).
- status: validated
- notes: 2× human actions ⇒ 0.25 score. The optimization target is *information per action*, not just
  task completion. Internal reasoning is free; actions are not.

### INS-003: The generalization gap is the central failure mode
- type: anti-pattern
- confidence: high
- evidence: StochasticGoose 12.58% on 6 known envs → 0.25% on the hidden set (`research.md` §2).
- transfer scope: AGI-3.
- status: validated
- notes: Only 25 of 135 envs are public. Anything that memorizes public envs dies on private. Favor
  in-episode adaptation + small prior-driven policies over per-env training.

### INS-004: Model-based RL is the only approach with a non-trivial public score
- type: hypothesis
- confidence: medium
- evidence: StochasticGoose (CNN + RL) is the best known public agent; frontier LLMs near-zero.
- transfer scope: AGI-3 approach selection (D002).
- status: candidate
- notes: Suggests the missing ingredient is grounded world-modeling + exploration, not more LLM
  reasoning tokens. Validate by prototyping RL vs LLM-harness on 2–3 public envs.

## Potentially reusable insights (cross-competition → `_shared/insights.md`)

### INS-005: Efficiency is scored in both AGI-2 and AGI-3 — optimize correctness-per-compute/action
- type: tactic
- confidence: high
- evidence: AGI-2 $0.42/task + 2 attempts; AGI-3 RHAE squares the action ratio. `cross-competition.md`.
- transfer scope: both ARC tracks (and arguably all our Kaggle work).
- status: candidate
- notes: Brute force loses in both. Build the reflex of minimizing wasted work per unit of score.

### INS-006: Offline gate must align with the online metric (carried from nemo)
- type: rule
- confidence: high
- evidence: nemo `_shared/insights.md` + `eval/official_metric.py`; here → build `eval/rhae.py` first.
- transfer scope: all competitions.
- status: validated
- notes: Don't iterate against a proxy that diverges from the leaderboard. For AGI-3, local RHAE over
  the 25 public envs before spending any daily submission quota.

### INS-007: Core-Knowledge priors are identical across AGI-1/2/3
- type: fact
- confidence: high
- evidence: AGI-3 restricts envs to objectness/geometry/topology/physics/agentness (`research.md` §3);
  same prior set underlies AGI-2 tasks.
- transfer scope: both ARC tracks — justifies a shared object-centric perception lib (T5).
- status: validated
- notes: Build the perception/prior front-end once in `_shared/`.
