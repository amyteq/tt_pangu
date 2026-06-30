# Tasks — ARC-AGI-3

## Now
- [ ] **T1 — SDK harness up.** Register API key at `three.arcprize.org`; `pip install arc-agi==0.9.9`;
  drive ≥ 3 of the 25 public envs in `terminal`/`human` render; record episodes (JSONL).
- [ ] **T2 — Local RHAE metric.** Implement `eval/rhae.py` computing `(human/agent actions)²` per
  level over the 25 public envs (need human-baseline action counts — pull from SDK scorecard / paper).
  *Prerequisite for measuring anything without burning daily quota* (nemo lesson: offline gate first).
- [ ] **T3 — Track decision (D001).** Read arXiv 2603.24621 §eval protocol; confirm Official-vs-Community
  qualification; pick a track. Recommendation: **Community first**.

## Next
- [ ] **T4 — Random + heuristic baseline.** Establish a non-zero RHAE floor; verify the full submission
  loop (one-click notebook, <12h, no-internet, `OperationMode.COMPETITION`).
- [ ] **T5 — Object-centric perception.** Segment 64×64 frames into Core-Knowledge objects → compact
  state. Shared candidate for `competitions/_shared/` (also useful for AGI-2).
- [ ] **T6 — Frame-predictor world model (H2).** Small net: (frame, action) → next frame; measure
  prediction accuracy on recorded episodes.
- [ ] **T7 — Information-greedy exploration (H1).** Intrinsic reward = world-model prediction error;
  compare RHAE vs random on held-out public envs.

## Backlog
- [ ] Model-based planner (MCTS / shooting) over the learned world model (D002).
- [ ] Meta-RL / in-episode adaptation (H3) — fast weights / RL² to learn each game live.
- [ ] Goal-inference module (detect win-state delta on tutorial → pursue on later levels).
- [ ] Community harness: orchestrator + subagents + selective history (Arcgentica/Duke patterns) over
  an **offline** open-weights reasoner.
- [ ] Hierarchical RL / skill discovery for compositional later levels.
- [ ] Procedural curriculum / self-play augmentation over the 25 public envs (anti-overfit).
- [ ] Reuse nemo Kaggle offline-pack tooling: `kca-arc-agi3.yaml` + on-the-fly metadata + flat
  `kernels/`+`lib/` + <12h guard + offline wheels (incl. Blackwell vLLM offline recipe).

## Blocked
- [ ] **Confirm ⚠ rules** (need Kaggle login): daily submission limit (retroactive "Team AIRIS" change),
  Kaggle GPU spec, `/data` download-vs-API, team-size cap, submission artifact contract. → `rules.md`.
- [ ] **API key** for `three.arcprize.org` (gates T1/T2). Suggest the user run an interactive login /
  key creation: `! pip install arc-agi==0.9.9` then follow the key flow.

## Done
- [x] **T0 — Workspace + research.** Created `competitions/arc-agi3/` from sourced research
  (ARC-AGI-3 + ARC-AGI-2 + cross-competition transfer). 2026-06-26.

## Proposed GitHub issues (not created here)
- "ARC-AGI-3: SDK harness + local RHAE metric (T1+T2)" — AC: drive ≥3 public envs, RHAE computed
  locally for a random baseline, episodes recorded.
- "ARC-AGI-3: decide Official vs Community track (D001)" — AC: documented decision + qualification
  evidence from arXiv 2603.24621.
- "Shared: object-centric grid perception lib for AGI-2 + AGI-3 (T5)" — AC: `_shared` lib parsing both
  30×30-int and 64×64-16color grids with object segmentation + tests.
