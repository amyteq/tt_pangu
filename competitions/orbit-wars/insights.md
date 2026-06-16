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

### INS-005: skill-rating ladders match SIMILAR-skill from the first game (no weak warmup)
- type: rule
- confidence: medium-high
- evidence: OW-P0-RESEARCH-001 — `ListEpisodes` over our subs 53582503 (n=239) + 53730511 (n=32): first game at μ0=600 vs opponent μ≈601; per-episode |opp−our| median ~43–66 and ~constant; opponent μ tracks ours as it climbs. Official skill-rating (pairwise μ-toward-mean). ~half the games 4p; 4p updates μ.
- transfer scope: any Kaggle simulation/skill-rating ladder
- operational: a new submission's first 10–20 episodes are INFORMATIVE (not inflated by weak matchups), so early μ trend is a fair-but-noisy read; don't assume a weak-first warmup. Bake into the live-loop decision (T24).

### INS-006: kuni05 (LB 1240.5) is rules + exact flow-diff, NOT a neural net
- type: fact
- confidence: high
- evidence: OW-P0-RESEARCH-001 — torch used only as vectorized algebra (no `torch.nn`/params/grads); `planner_core.py:75-86` pure me−opp; `garrison_launch.py:311-450` exact sparse recurrence. Study: `discussions/2026-06-16-kuni05-system-study.md`.
- transfer scope: the strong-tier edge is an integrated heuristic SYSTEM (safe_drain max-shed sizing + multi-wave + role-mutex + regroup + exact oracle), not learning — consistent with our 13-lever refutation + Phase-0 (planner=greedy under conservation value).

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
