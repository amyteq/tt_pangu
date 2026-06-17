# Insights — Orbit Wars

## Competition-specific insights
- **Official `garrison+1` baseline is wrong for moving/producing targets** — neutrals are static but enemy
  planets grow by `production*travel_ticks`; lead the growth. Evidence: `README.md` (exact capture rule, engine refs).
- **Terminal (k=H) differential net-ship value is conservation-correct** — scoring over all k penalizes ships
  still in transit. This was the one big lever (556→686). Evidence: `README.md` (Forecast key bug).
- **少而重 > 多而小** — concentrated strikes (e.g. 27×78 ships) beat many small ones (117×19); ~56% of a top
  winner's launches are short-hop reinforcement (supply chain). Evidence: `EPISODES.md` #1 (Jake Will).
  *Does not transplant:* OVERKILL multiplier, T14 supply, and the 2026-06-16 v4a/v4f/v4c/v4i revivals all failed
  the gate — concentration is emergent, and v4 can't reach the top-tier board states where it pays (~1–2% vs
  kuni05). Evidence: `postmortems/2026-06-16-overkill-revival.md`.
- **Top-6 are rule/search engines, no NN** — behavior cloning reproduces the *form* not the *system*
  (T12: recall@k 0.387 but 0% in arena). Evidence: `EPISODES.md` #2; issue #87 (T12 v2).
- **Strong tier wins as integrated systems** — **12** transplanted single-mechanism levers all failed on the suite
  (incl. v4a counter-attack window, v4f best-response value, v4c cluster hammer, v4i Isaiah two-band, and **T20
  early-massing `OW_EM`** 2026-06-16: opening capture-and-hold sizing, monotonic-negative vs evogen −7.5→−13.8pt,
  no positive region — `postmortems/2026-06-16-t20-early-massing.md`). The 多而小 opening gap is real (ep 80118852)
  but bigger opening fleets over-commit and lose the ship race; the fix is an INTEGRATED opening planner, not a knob.
- **Rotation is NOT a free transport lever (relay/staging refuted, 2026-06-16).** Inner planets rotate at
  ω∈[0.025,0.05] (`orbit_wars.py:540-546`); a planet's max radial closing speed toward a target = orbital_r·ω
  ≈ 2.35 u/step at the inner-ring edge — *below* even a 19-ship fleet's 2.39 u/step. So flying always beats
  "riding the orbit", the optimal relaunch delay computed to 0 in every geometry/ω, and the orbital
  minimum-distance phase is 170–210 steps out (games end ~150). The honest 2-hop (ship O→I then relaunch) is
  strictly worse (35–39 vs 27 turns direct); 2-hop only "wins" when the staging planet is ALREADY held and
  closer to T — pure geometry, not rotation. **The real value of "少而重" is the source-side massing speedup**
  (`speed=1+(maxSpeed-1)(ln n/ln1000)^1.5`, `:577`: 19→2.39, 76→3.48 = +46%) + the strict per-arrival capture
  threshold — obtainable with no hop. → PARK rotation-relay; see `tasks.md` T20/T21.
- **Local arena reliability is tier-coarse, cluster-blind (calibrated 2026-06-16).** Win% vs evogen tracks the
  GROSS ladder ordering (kuni05 90% / μ1083 ≫ our line ≤20% / μ640–686 ≫ v2.1 0% / μ556) but cannot finely
  rank within our cluster (v3 μ686 and v3.2 μ640 BOTH 16.7%). ⇒ use the arena to gate against the strong tier,
  but use the REAL ladder for fine candidate selection (the orbit5 submit policy). v4 = our best-of-line at 20.0%.
- **`flyingfox` = harrysun2006 (our profile name), NOT external (corrected 2026-06-16).** Sub 53582503 = our
  `submission_kuni.tar.gz` (adapted kuni05, μ~1080). So tracking.md's "flyingfox 205-episode history" 4p-format
  finding + EPISODES.md #3 analyzed OUR OWN account (finding stands; "external" label was wrong — re-label #3).
- **Our kuni05 plays 多而小 EARLY, 少而重 only LATE (episode 80118852, our 4p WIN).** Seat-1 (=us) launch median
  by phase: early ≤80 = **20 ships** (74 launches, behind 5 vs 7 planets at step40); mid 81–160 = 36; late >160 =
  **238** (max 467). We overtook ~step100 and ground out the win after rivals imploded. So even our STRONGEST agent
  expands with many small fleets early and masses only late — vs the strong tier (no collapse) that loses games.
  **Lever: mass earlier from the opening (few-but-heavy), don't grind** (T20/T21). 41% of launches from
  inner(rotating) planets (inner=44% of map) → uses them ~proportionally, no staging bias (corroborates relay PARK).
  Evidence: `replays/80118852.json` + `ListEpisodes(53582503)`.

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
- confidence: high
- evidence: **triple-confirmed.** (1) T12 BC: recall@k 0.387 / 0% arena. (2) prompt-05 local-data
  scorer: AUC 0.92 offline / untested. (3) prompt-06 REAL-ladder scorer: AUC 0.882 offline, wired as
  a candidate re-ranker → strong-tier arena FLAT (vs evogen 13.8%→13.8–14.6%, vs kuni05 0.8%→0.8% over
  240g/cell). Offline imitation fidelity does not predict ladder strength.
- transfer scope: imitation-learning on planning/agent tasks
- status: validated — gate every model on arena A/B (VALIDATION #3), never on AUC/recall@k

### INS-004: parallel arena — engine is CPU-bound, GPU useless
- type: fact
- confidence: high
- evidence: `arena/pool.py` (~30–40× across cores; deterministic)
- transfer scope: pure-Python simulation competitions
- status: validated

### INS-007: deterministic execution core + typed BattlefieldState as the hybrid substrate
- type: rule
- confidence: high
- evidence: OW-P0-STATE-LEDGER-001 — `core/{geometry,oracle,ledger,state,features,rule_engine}.py`
  built on the engine-verified primitives; FlightOracle gives a single deterministic first-hit/
  target-validation gate (tests 6/6), BattlefieldState/ledger give typed awareness (tests 5/5),
  RuleEngine hard-blocks unsafe launches + tactically re-weights. `arena/validate.py` clean.
- transfer scope: any agent/hybrid task — keep continuous-control execution deterministic + tested,
  let the model only rank/score candidates (never own raw angle/landing). This is the foundation the
  strong-tier cliff attack needs; bolt-on single levers failed (13×, INS-005/strategy.md H2) precisely
  because there was no integrated state+execution layer for an integrated policy to sit on.

### INS-008: a re-ranker over your own candidates can't add strategy you don't generate
- type: rule
- confidence: high
- evidence: prompt-06 hybrid_v0 — a model scorer blended into v3.2's greedy commit order changed
  ~6.5% of decisions yet moved strong-tier win% by ~0 (vs evogen/kuni05, 240g/cell). kuni05 beats
  v3.2 0.8% with a ~135× score margin — a different strategy, not a better ordering of v3.2's moves.
  The strong-tier cliff (B6) is a candidate-GENERATION / strategy gap, not a candidate-RANKING gap.
- transfer scope: hybrid model+rules agents — if the rule base can't propose the winning move, no
  scorer can pick it. Put model capacity where the gap is (generation/search/value), not just ranking.
- status: validated

### INS-009: the strong-tier cliff vs evogen was substantially a FUNDAMENTAL SIM BUG, not only strategy
- type: fact
- confidence: high
- evidence: user-reported fleet-into-sun (ep 80276901) traced to an off-by-one planet-rotation phase
  (B11): the engine observes orbiting planets at `rotate(init, ang_vel*max(0,step-1))` but all our
  predictors used `ang_vel*step` (one tick ahead). Fixing it (`core/geometry.planet_pos` +
  `agent/main.py._planet_pos`/`._predict_pos`): fixed-v3.2 beats frozen-buggy-v3.2 **95%** (200g) and
  jumps **vs evogen1093 13.8% → 45.0%** (+31pt, 200g); fixed agent sun launches 0%, oob 0.5% (was ~9%).
  4p avg_rank 1.72/4. (kuni05 still ~1% — a separate gap.)
- transfer scope: simulation-based agents — BEFORE attributing a plateau to "strategy", verify the
  forward model is BIT-EXACT vs the engine on multi-step rotation/phase (13 strategy levers + a model
  were refuted chasing this cliff; the real cause was a 1-tick phase error masked because the error
  (~orbit_r*ang_vel≈1.6u) is < planet radius so most captures still worked). Validate predictors
  against real replays (`_predict_pos(t-1)==obs(t)`), not just unit cases.
- status: validated — partially revises INS-008 (ranking wasn't the only gap; the candidate GENERATOR
  was mis-aiming). Re-evaluate the model/hybrid on FIXED-sim data.
