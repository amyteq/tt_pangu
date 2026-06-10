# Orbit Wars — KCA competition workspace

Kaggle **Orbit Wars** ($50,000 Featured, deadline **2026-06-23**, ~4137 teams).
Agent-vs-agent RTS on `kaggle_environments`; ranked by a rolling TrueSkill-style
score (LB top ≈ 1732, top-10 ≈ 1500–1600 as of 2026-06-10).

## Layout

```
competitions/orbit-wars/
  agent/main.py        # the submission agent (single-file; stdlib + kaggle_environments only)
  agent/versions/*.py  # frozen snapshots (v1, v2, v2_1) for head-to-head regression
  arena/pool.py        # parallel engine: fans independent games across CPU cores
  arena/arena.py       # round-robin / head-to-head on the REAL engine (offline gate)
  arena/validate.py    # held-out validation on fresh seeds
  arena/sweep.py        # garrison/cap sweep, gated vs v1 snapshot
  arena/sweep_phase.py  # phase-scaled cap sweep, gated vs v2 snapshot
  arena/diagnose.py    # single-game loss tracer
  README.md            # this file
```

The engine is pure-Python and CPU-bound (a GPU does not help); wall-clock is just
running many 500-step games. `arena/pool.py` parallelizes across cores — on a 24-core
box, ~96 games run in ~8s (≈30-40x serial). Results are **deterministic and identical
to serial** (each game is seeded; verified procs=1 vs procs=12), except against the
inherently-random `random` agent. All arena tools take `--games`, `--procs`, `--base`
(first seed). To run on the RTX 4090 box (snorlax), use its CPU cores via `--procs`.

## Ground truth

The engine is installed locally and is the source of truth (do not re-derive from
the web competition page, which is JS-rendered and unreadable by fetchers):

`…/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`

Key mechanics we exploit (with engine line refs):
- **Deterministic orbits** (`orbit_wars.py:540-546`): a planet's position at any step is
  `angle = atan2(iy-50, ix-50) + angular_velocity * step`. We predict exact arrival
  positions and solve a real intercept instead of aiming at stale coordinates.
- **Exact capture rule** (`:667-674`): a single attacker captures iff
  `ships > garrison_at_arrival` (strict). Neutrals don't produce; enemy planets gain
  `production * travel_ticks` (`:512-514`). So the official `garrison+1` baseline is
  *wrong* for moving/producing targets — we lead the growth.
- **First-hit consumption** (`:588-598`): a fleet is consumed by the FIRST planet its
  swept path touches, and dies on the sun / out-of-bounds (`:602-609`). Launch angles
  must avoid friendly/neutral bodies and the sun, or the whole fleet is wasted.
- **Combat sums same-owner fleets arriving the same tick** (`:642-665`): "largest minus
  second-largest survives"; ties annihilate. Synchronized multi-fleet arrival is a real
  lever (planned for v2).

## Agent versions

### v2.1 — "Phase-Scaled" (current best; `agent/main.py`, snapshot `agent/versions/v2_1.py`)

v2's in-flight cap is flat (1.2×). v2.1 makes it phase-dependent: looser early to win
the land-grab, tighter late to hold and bank — `cap(step) = lerp(CAP_EARLY, CAP_LATE)`.
A gated sweep vs the frozen flat-1.2 v2 snapshot (`OW_CAP_EARLY`/`OW_CAP_LATE` only affect
the candidate; v2.py predates those knobs) found **2.0 → 1.0** best (60% on tuning seeds);
*mild* scaling won, aggressive scaling (2.5-3.0 early / 0.6-0.8 late) all lost.

**Validation on 24 FRESH seeds (4000+, unused in any tuning), x2 orderings:**

| Matchup            | Record  | Win%  |
|--------------------|---------|-------|
| v2.1 vs v2 (the bar)| 26-22-0 | 54.2  |
| v2.1 vs v1         | 39-9-0  | 81.2  |
| v2.1 vs starter    | 39-9-0  | 81.2  |
| v2.1 vs random     | 48-0-0  | 100.0 |

**Confidence note (honest, updated after a 200-game confirmation):** phase-scaling is a
**wash on win-rate, not a real improvement.** vs-v2: 60% (40g tuning) → 54.2% (48g held-out)
→ **52.5% (200g confirmation)**; aggregate 155-133 = 53.8% over 288 games (one-sided
p ≈ 0.10, 95% CI on the 200g run ≈ [45.6%, 59.4%] — includes 50%). The edge shrank toward
50% as n grew (regression to the mean). v2.1 *does* end with a higher avg ship count
(1709 vs 1469), but LB reward is win/loss, not margin. Kept only because it's harmless and
slightly more flexible — **cap-tuning has hit diminishing returns; further gains need a
structurally different lever (consolidation, synchronized strikes, search) tested against
STRONGER/more diverse opponents, not flat-1.2 self-play.** Defaults `CAP_EARLY=2.0`,
`CAP_LATE=1.0` (`OW_*`-overridable).

### v2 — "Hold What You Take" (superseded; snapshot `agent/versions/v2.py`)

Diagnosis of v1's only losses (deterministic on map seed 1007, both seat orderings):
v1 captured 41 planets but *lost 39*, peaking at **756 ships in flight** while holding
only **~13 ships/planet** (starter held ~30). Root cause: v1's reserve was 0 whenever no
fleet was *currently* inbound and it sent "exactly enough", so every captured planet sat
at ~0 garrison and was retaken — a capture-churn loop that bled ships in transit while
starter banked and out-produced (classic leaky expansion).

A first heavy-handed fix (large garrison + 0.55 in-flight cap) **over-corrected** — it lost
to v1 (21.9%) because it killed the fast expansion that wins most maps. An arena sweep
(gate: must beat the frozen v1 snapshot head-to-head) found the real lever is a **mild
in-flight cap** plus a *small* frontier garrison:

- `INFLIGHT_CAP_FRAC = 1.2` — total in-flight ships may not exceed 1.2× ships-on-planets
  (v1 reached ~5×). Preserves aggression, kills over-commitment. **This is the decisive lever.**
- `FRONTIER_FLOOR = 10` — planets within 28 units of an enemy keep a small standing garrison.
- `REAR_FLOOR = 0` — rear planets stay fully aggressive.

(All tunables are `OW_*` env-overridable for sweeps; baked defaults are the tuned values.)

**Validation on 20 FRESH seeds (3000-3019, unused in tuning), x2 orderings:**

| Matchup            | Record  | Win%  |
|--------------------|---------|-------|
| v2 vs `starter`    | 37-3-0  | 92.5  |
| v2 vs `random`     | 40-0-0  | 100.0 |
| v2 vs v1 (h2h)     | 30-10-0 | 75.0  |
| seed 1007 (was a loss) | win both orderings | ✅ |

### v1 — "Intercept Economist" (superseded; snapshot `agent/versions/v1.py`)

Economic expansion with: deterministic position prediction → fixed-point intercept
solver → exact capture math (neutral static vs enemy growth) → sun/planet path
avoidance → light inbound-fleet defensive reserve → greedy global allocation (each
target committed once, ranked by production-per-ship discounted by travel time).
Wrapped so any error returns `[]` (passive but alive — never forfeits on a crash).

**Offline results** (`python arena/arena.py --games 8`, 16 games/matchup, real engine):

| Matchup            | Record    | Win%  | Avg score      |
|--------------------|-----------|-------|----------------|
| v1 vs `random`     | 16-0-0    | 100.0 | 2453 vs 0      |
| v1 vs `starter`    | 14-2-0    |  87.5 | 1924 vs 636    |
| `starter` vs `random` (sanity) | 16-0-0 | 100.0 | — |

Per-turn cost ≈ **0.72 ms** on the densest state (28 planets / 60 fleets); budget is
1000 ms → ~1380× headroom for future search.

### Roadmap (v3+ ideas, by expected impact)

1. ~~Investigate the 2 losses to `starter`~~ — **done → v2** (leaky expansion; fixed by
   in-flight cap + frontier garrison; see v2 above).
2. ~~Per-game-phase cap scaling~~ — **done → v2.1** (2.0→1.0; small consistent edge, ~wash
   on a 200g confirmation). A finer frontier-param sweep is still open.
3. ~~Consolidation (forward idle rear surplus)~~ — **TRIED → REJECTED, default OFF**
   (`arena/sweep_consol.py`). Never beats v2.1: −20pts when aggressive (min=12: 30% vs v2.1),
   neutral when rare (min≥30: 40-40). Forwarding wastes transit, starves the in-flight cap,
   and funnels launch points; our aggression already uses rear ships well. Code kept,
   env-gated (`OW_CONSOLIDATE=1`) for reproducibility. **Calibration note:** identical-mirror
   matches tie often (~18/80), so the "no-edge" win% is ~39%, not 50% — read decisive W-L.
4. **Real targeted defense** — predict inbound impact planet + tick precisely (swept test)
   and reinforce the *specific* threatened planet from neighbors, vs the current flat floor.
5. **Synchronized strikes** — exploit same-tick same-owner summing: stage fleets from several
   planets to co-arrive on a hard target (distinct from consolidation — keep launch points,
   just time the arrivals; bigger fleets are also faster).
6. **Comet play** — capture/deny comets near our territory for temp production (they leave
   with their ships at the path end; bounded investment).
7. **Time-bounded lookahead** — with ~1000× budget headroom, a 1–3 ply search with a
   production-weighted control eval over a small `(target × ship-fraction)` action set.

## Sparring opponents

Self-play vs our own variants has low information about real standing, so we pull strong
public agents as gate opponents (`arena/_extract_pub.py <notebook.ipynb> <out.py>` lifts a
notebook's `%%writefile submission.py` cell into a runnable file).

- **`agent/versions/pub_tactical.py`** — sigmaborov "Tactical Heuristic 2026" (lead-aim,
  sun-avoidance waypoint routing, comet prediction, a full planet-future combat simulator,
  net-defense reserve). Pure heuristic, **1.6 ms/turn**, runs clean (0 errors in audit).
  Baseline (120 games each, 60 seeds x2): **v2.1 beats it 90.8%** (avg 5449 vs 291),
  v1 89.2%, and it beats `starter` 55-45. So strength order is `v2.1 > pub_tactical > starter`
  — a legitimate non-trivial opponent, but we already dominate it, so it weakly discriminates
  small tweaks. Useful as a sanity gate; not a hard teacher.

### 4-player coverage (`arena/arena4.py`)

The env supports 2 AND 4 players (`make("orbit_wars").specification.agents == [2, 4]`), so we
test both. 4p metric = hero win-rate (placed 1st of 4; ties-for-first count) + avg finishing
rank (1=best). The hero is rotated through all 4 seats per seed for fairness.

Baseline (120 games each, 30 seeds x4 seats, base 6000):

| Hero = v2.1, field | Win% | Avg rank |
|--------------------|------|----------|
| vs 3x random       | 100  | 1.00 |
| vs 3x pub_tactical | 90.8 | 1.09 |
| vs 3x starter      | 65.8 | 1.34 |
| vs [pub,v1,starter]| 41.7 | 1.62 |
| vs 3x v2.1 (mirror)| 57.5 | 1.59 |
| pub_tactical vs 3x starter | 25.8 | 1.79 |

**Resolved:** our 2p strength transfers — v2.1 wins 1.7-2.6x its fair share vs every non-trivial
4p field and finishes near rank 1. Aggression works in crowds too.

**Two calibration notes:**
- The 4-identical **mirror gives ~57.5%, not 25%** — a seat tied for first counts as a win and
  symmetric play yields frequent top-ties. So in 4p, **~57% is the "no-edge" null** for comparing
  near-identical agents; prefer `avg_rank` as the discriminator there.
- **pub_tactical ≈ random-level in 4p** (25.8% vs starters); its careful 2p play doesn't scale to
  crowds. For 4p stress-testing, `3x starter` is the harder field.

**RESOLVED — the scored ladder is 1v1 (2-player).** From the rendered competition pages
(`kaggle competitions pages orbit-wars --content`, kaggle CLI >= 2.x):
- Abstract: *"...AI bots to play a novel multi-agent **1v1 or 4p FFA** game..."* — the engine
  supports both modes.
- Evaluation / skill-rating update: *"If one Submission won, we'll increase its μ and decrease
  **its opponent's** μ ... move **the two μ values** closer towards their mean."* The update is
  **pairwise** (singular "opponent", "the two μ values"), and the validation episode plays
  "against copies of itself" — i.e. the ranked ladder runs **2-player** episodes.

Implication: our extensive **2p** testing is the right LB proxy (v2.1 beats the strongest public
agent we found ~91% in 2p). The 4p arena is kept for robustness/optional, not the primary gate.
(Competition id 138420; deadline 2026-06-23, final eval ~2 weeks after; up to 5 submissions/day,
latest 2 tracked, μ0=600 skill-rating ladder.)

## Running

```bash
cd competitions/orbit-wars
python arena/arena.py                          # default suite (current vs baselines), auto procs=cpu-1
python arena/arena.py --games 32 --procs 23    # bigger, pin worker count
python arena/arena.py --a v2.1 --b v1          # head-to-head (names: random/starter/v1/v2/v2.1 or a path)
python arena/validate.py --games 40 --base 5000  # held-out validation on unseen seeds
python arena/sweep_phase.py --games 40         # gated param sweep (parallel)
```

## Submission policy (per CLAUDE.md)

- Submitting to Kaggle is a **remote write requiring explicit human approval**. This
  workspace is offline-only until approved.
- **Gate**: only submit a version that beats the current best agent in the local arena by
  a clear margin over many seeds (mirrors the KCA autonomous-submission strategy).
- Submit command (when approved): `kaggle competitions submit orbit-wars -f agent/main.py -m "..."`.
- Rules must be accepted on the website first (account already joined).
```
