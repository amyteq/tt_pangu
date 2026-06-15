# Insights — Orbit Wars

## Competition-specific insights
- **Official `garrison+1` baseline is wrong for moving/producing targets** — neutrals are static but enemy
  planets grow by `production*travel_ticks`; lead the growth. Evidence: `README.md` (exact capture rule, engine refs).
- **Terminal (k=H) differential net-ship value is conservation-correct** — scoring over all k penalizes ships
  still in transit. This was the one big lever (556→686). Evidence: `README.md` (Forecast key bug).
- **少而重 > 多而小** — concentrated strikes (e.g. 27×78 ships) beat many small ones (117×19); ~56% of a top
  winner's launches are short-hop reinforcement (supply chain). Evidence: `EPISODES.md` #1 (Jake Will).
  *Does not transplant:* OVERKILL multiplier, T14 supply, and the 2026-06-16 v4a/v4f revivals all failed the
  gate — concentration is emergent, and v4 can't reach the top-tier board states where it pays (~1% vs kuni05).
  Evidence: `postmortems/2026-06-16-overkill-revival.md`.
- **Top-6 are rule/search engines, no NN** — behavior cloning reproduces the *form* not the *system*
  (T12: recall@k 0.387 but 0% in arena). Evidence: `EPISODES.md` #2; issue #87 (T12 v2).
- **Strong tier wins as integrated systems** — 9 transplanted single-mechanism levers all failed on the suite
  (incl. v4a counter-attack window & v4f best-response value, 2026-06-16).

## Potentially reusable insights

### INS-001: ladder-predictive offline suite (not self-play)
- type: rule
- confidence: high
- evidence: `README.md` / issue #87 (self-play 91% but ≈ on ladder; suite gate aligned)
- transfer scope: any competition with a hidden ladder / online eval
- status: validated (this competition); logged in `_shared/skill-candidates.md` (ladder-predictive-gate)

### INS-002: powered paired-seed A/B + bake gate (kill small-sample false positives)
- type: rule
- confidence: high
- evidence: issue #87 (batch noise 8–27%; ≥150 paired seeds ±3.5pt; +7pt bake gate caught a would-be regression)
- transfer scope: any stochastic-eval optimization
- status: validated

### INS-003: imitation/BC ≠ playing for integrated-system opponents
- type: anti-pattern
- confidence: medium
- evidence: issue #87 (T12 high imitation, 0% arena — distribution shift)
- transfer scope: imitation-learning on planning/agent tasks
- status: candidate

### INS-004: parallel arena — engine is CPU-bound, GPU useless
- type: fact
- confidence: high
- evidence: `arena/pool.py` (~30–40× across cores; deterministic)
- transfer scope: pure-Python simulation competitions
- status: validated
